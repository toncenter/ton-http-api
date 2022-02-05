import inject
import sys
import pandas as pd

from typing import Optional
from pymongo import MongoClient

from fastapi import FastAPI
from fastapi.params import Query

from config import settings
from anTON.utils import _read_requests, _read_liteserver_tasks, _compute_stats

from loguru import logger


# inject configure
def inject_config(binder):
    client = MongoClient(**settings.mongodb)

    binder.bind(MongoClient, client)
    logger.info(f"Injector configuration complete")


inject.configure_once(inject_config)


# FastAPI app
description = """Analytics API in-dev"""


app = FastAPI(
    title="Analytics API",
    description=description,
    docs_url='/',
    responses={},
    root_path='/analytics/api/v0',
)


@app.on_event("startup")
def startup():
    logger.remove(0)
    logger.add(sys.stdout, level='INFO', enqueue=True)
    logger.add('/var/log/analytics.log', 
               level='INFO', 
               enqueue=True,
               serialize=False,
               backtrace=False,
               rotation='2 weeks')


# request statistics

@app.get('/requests', response_model_exclude_none=False)
def request_stats(period: str=Query(..., 
                                    description='Get requests statistics for period, '
                                                'pass string in format: <days>d<hours>h<minutes>m<seconds>s', 
                                    example='1h'),
                  by_method: bool=Query(False, description='Aggregate data by method'), 
                  by_status_code: bool=Query(False, description='Aggregate data by status code'),
                  # by_ip: bool=Query(False, description='(TBD) Aggregate data by client ip'),
                  end_timestamp: Optional[float]=Query(None, description='Set end timestamp (use UTC)')):
    # perpare index
    index = []
    if by_method:
        index.append('url')
    # if by_ip:
    #     index.append('from_ip')
    #     raise NotImplementedError("(WIP) Not allowed without authentification")
    if by_status_code:
        index.append('status_code')
    
    # read data
    data = _read_requests(period, end_timestamp=end_timestamp)
    if data.shape[0] == 0:
        return []
    
    # compute stats
    stats = _compute_stats(data, index)
    return stats.to_dict(orient='records')


# liteserver task statistics
@app.get('/liteservers', response_model_exclude_none=False)
def liteserver_task_stats(period: str=Query(..., 
                                            description='Get liteserver tasks statistics for period, '
                                                        'pass string in format: <days>d<hours>h<minutes>m<seconds>s', 
                                            example='1h'),
                          by_method: bool=Query(False, description='Aggregate data by method'), 
                          by_status_code: bool=Query(False, description='Aggregate data by status code'),
                          by_archival: bool=Query(False, description='Aggregate data by archival/non-archival liteservers'),
                          end_timestamp: Optional[float]=Query(None, description='Set end timestamp (use UTC)')):
    # perpare index
    index = []
    if by_method:
        index.append('method')
    if by_status_code:
        index.append('status')
    if by_archival:
        index.append('archival_liteserver')
    
    # read data
    data = _read_liteserver_tasks(period, end_timestamp=end_timestamp)
    if data.shape[0] == 0:
        return []
    
    # compute stats
    stats = _compute_stats(data, index)
    return stats.to_dict(orient='records')


# healthcheck
@app.get('/healthcheck', response_model_exclude_none=False)
def healthcheck():
    return {'status': 'ok'}
