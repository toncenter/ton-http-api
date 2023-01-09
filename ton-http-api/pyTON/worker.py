import asyncio
import random
import sys
import time
import queue
import multiprocessing as mp

from pyTON.settings import TonlibSettings
from pyTON.models import TonlibWorkerMsgType, TonlibClientResult
from pytonlib import TonlibClient, TonlibException, BlockNotFound
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Optional

from loguru import logger


class TonlibWorker(mp.Process):
    def __init__(self, 
                 ls_index: int, 
                 tonlib_settings: TonlibSettings,
                 input_queue: Optional[mp.Queue]=None,
                 output_queue: Optional[mp.Queue]=None):
        super(TonlibWorker, self).__init__(daemon=True)

        self.input_queue = input_queue or mp.Queue()
        self.output_queue = output_queue or mp.Queue()
        self.exit_event = mp.Event()

        self.ls_index = ls_index
        self.tonlib_settings = tonlib_settings

        self.last_block = -1
        self.is_archival = False
        self.semaphore = None
        self.loop = None
        self.tasks = {}
        self.tonlib = None
        self.threadpool_executor = None

        self.timeout_count = 0
        self.is_dead = False

    def run(self):
        self.threadpool_executor = ThreadPoolExecutor(max_workers=16)

        policy = asyncio.get_event_loop_policy()
        policy.set_event_loop(policy.new_event_loop())
        self.loop = asyncio.new_event_loop()

        Path(self.tonlib_settings.keystore).mkdir(parents=True, exist_ok=True)

        # init tonlib
        self.tonlib = TonlibClient(ls_index=self.ls_index,
                                   config=self.tonlib_settings.liteserver_config,
                                   keystore=self.tonlib_settings.keystore,
                                   loop=self.loop,
                                   cdll_path=self.tonlib_settings.cdll_path,
                                   verbosity_level=self.tonlib_settings.verbosity_level)

        try:
            self.loop.run_until_complete(self.tonlib.init())
        except Exception as e:
            logger.error("TonlibWorker #{ls_index:03d} failed to init and sync tonlib: {exc}", ls_index=self.ls_index, exc=e)
            self.shutdown(11)

        # creating tasks
        self.tasks['report_last_block'] = self.loop.create_task(self.report_last_block())
        self.tasks['report_archival'] = self.loop.create_task(self.report_archival())
        self.tasks['main_loop'] = self.loop.create_task(self.main_loop())
        self.tasks['sync_tonlib'] = self.loop.create_task(self.sync_tonlib())

        finished, unfinished = self.loop.run_until_complete(asyncio.wait([
            self.tasks['report_last_block'], self.tasks['report_archival'], self.tasks['main_loop'], self.tasks['sync_tonlib']], return_when=asyncio.FIRST_COMPLETED))

        self.shutdown(0 if self.exit_event.is_set() else 12)

    def shutdown(self, code: int):
        self.exit_event.set()
        
        for task in self.tasks.values():
            task.cancel()
            try:
                self.loop.run_until_complete(to_cancel)
            except:
                pass

        self.threadpool_executor.shutdown()

        self.output_queue.cancel_join_thread()
        self.input_queue.cancel_join_thread()
        self.output_queue.close()
        self.input_queue.close()
        sys.exit(code)

    @property
    def info(self):
        return {
            'ip_int': f"{self.tonlib_settings.liteserver_config['liteservers'][self.ls_index]['ip']}",
            'port': f"{self.tonlib_settings.liteserver_config['liteservers'][self.ls_index]['port']}",
            'last_block': self.last_block,
            'archival': self.is_archival,
            'number': self.ls_index,
        }

    async def report_last_block(self):
        while not self.exit_event.is_set():
            last_block = -1
            try:
                masterchain_info = await self.tonlib.get_masterchain_info()
                last_block = masterchain_info["last"]["seqno"]
                self.timeout_count = 0
            except TonlibException as e:
                logger.error("TonlibWorker #{ls_index:03d} report_last_block exception of type {exc_type}: {exc}", ls_index=self.ls_index, exc_type=type(e).__name__, exc=e)
                self.timeout_count += 1

            if self.timeout_count >= 10:
                raise RuntimeError(f'TonlibWorker #{self.ls_index:03d} got {self.timeout_count} timeouts in report_last_block')
            
            self.last_block = last_block
            await self.loop.run_in_executor(self.threadpool_executor, self.output_queue.put, (TonlibWorkerMsgType.LAST_BLOCK_UPDATE, self.last_block))
            await asyncio.sleep(1)

    async def report_archival(self):
        while not self.exit_event.is_set():
            try:
                block_transactions = await self.tonlib.get_block_transactions(-1, -9223372036854775808, random.randint(2, 4096), count=10)
                self.is_archival = True
            except BlockNotFound as e:
                self.is_archival = False
            except TonlibException as e:
                logger.error("TonlibWorker #{ls_index:03d} report_archival exception of type {exc_type}: {exc}", ls_index=self.ls_index, exc_type=type(e).__name__, exc=e)
            
            await self.loop.run_in_executor(self.threadpool_executor, self.output_queue.put, (TonlibWorkerMsgType.ARCHIVAL_UPDATE, self.is_archival))
            await asyncio.sleep(600)
        
    async def main_loop(self):
        while not self.exit_event.is_set():
            try:
                task_id, timeout, method, args, kwargs = await self.loop.run_in_executor(self.threadpool_executor, self.input_queue.get, True, 1)
            except queue.Empty:
                continue

            self.loop.create_task(self.process_task(task_id, timeout, method, args, kwargs))

    async def process_task(self, task_id, timeout, method, args, kwargs):
        result = None
        exception = None

        start_time = datetime.now()
        if time.time() < timeout:
            try:
                result = await self.tonlib.__getattribute__(method)(*args, **kwargs)
            except Exception as e:
                exception = e
                logger.warning("TonlibWorker #{ls_index:03d} raised exception of type {exc_type} while executing task. Method: {method}, args: {args}, kwargs: {kwargs}, exception: {exc}", 
                    ls_index=self.ls_index, method=method, args=args, kwargs=kwargs, exc_type=type(e).__name__, exc=e)
            else:
                logger.debug("TonlibWorker #{ls_index:03d} got result {method} for task '{task_id}'", ls_index=self.ls_index, method=method, task_id=task_id)
        else:
            exception = asyncio.TimeoutError()
            logger.warning("TonlibWorker #{ls_index:03d} received task '{task_id}' after timeout", ls_index=self.ls_index, task_id=task_id)
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        # result
        tonlib_task_result = TonlibClientResult(task_id,
                                                method,
                                                elapsed_time=elapsed_time,
                                                params=[args, kwargs],
                                                result=result,
                                                exception=exception,
                                                liteserver_info=self.info)
        await self.loop.run_in_executor(self.threadpool_executor, self.output_queue.put, (TonlibWorkerMsgType.TASK_RESULT, tonlib_task_result))

    async def sync_tonlib(self):
        await self.tonlib.sync_tonlib()

        while not self.exit_event.is_set():
            await asyncio.sleep(1)
