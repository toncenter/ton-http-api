import inject
import traceback

from collections.abc import Mapping
from abc import abstractmethod

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response, StreamingResponse
from starlette.types import Message

from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from json import loads

from pyTON.models import TonResponse, TonlibClientResult
from pyTON.settings import Settings, MongoDBSettings, LoggingSettings, MongoDBLoggingSettings

from typing import Optional

from loguru import logger


class LoggingManager:
    def log_liteserver_task(self, task_result: TonlibClientResult, *args, **kwargs) -> None:
        pass

    def log_worker_status(self, worker_stats, *args, **kwargs) -> None:
        pass


class DisabledLoggingManager(LoggingManager):
    pass


class MongoLoggingManager(LoggingManager):
    def __init__(self, logging_settings: MongoDBLoggingSettings, *args, **kwargs):
        self.mongo_client = MongoClient(host=logging_settings.mongodb.host,
                                        port=logging_settings.mongodb.port,
                                        username=logging_settings.mongodb.username,
                                        password=logging_settings.mongodb.password)
        self.database = logging_settings.mongodb.database
        self.mongo_client[self.database]['liteserver_tasks'].create_index('timestamp', expireAfterSeconds=logging_settings.record_ttl)

    def log_liteserver_task(self, task_result: TonlibClientResult, *args, **kwargs):
        res_type = None
        if isinstance(task_result.result, Mapping):
            res_type = task_result.result.get('@type', 'unknown') if task_result.result else 'error'
        else:
            result_type = 'list'
        details = {}
        if res_type == 'error' or res_type == 'unknown':
            details['params'] = [str(p) for p in task_result.params]
            details['result'] = task_result.result
            details['exception'] = str(task_result.exception)
        
        rec = {
            'timestamp': datetime.utcnow(),
            'elapsed': task_result.elapsed_time,
            'task_id': task_result.task_id,
            'method': task_result.method,
            'liteserver_info': task_result.liteserver_info,
            'result_type': res_type,
            'details': details,
        }
        self.mongo_client[self.database]['liteserver_tasks'].insert_one(rec)
        logger.info("Received result of type: {result_type} task_id: {task_id} method: {method}", **rec)

    def log_worker_status(self, worker_stats, *args, **kwargs) -> None:
        pass

