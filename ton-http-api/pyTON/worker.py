import asyncio
import traceback
import random
import time
import aioprocessing as ap
import multiprocessing as mp

from pyTON.settings import TonlibSettings
from pyTON.models import TonlibWorkerMsgType, TonlibClientResult
from pytonlib import TonlibClient
from datetime import datetime

from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Optional

from loguru import logger


class TonlibWorker(mp.Process):
    def __init__(self, 
                 ls_index: int, 
                 tonlib_settings: TonlibSettings,
                 input_queue: Optional[ap.AioQueue]=None,
                 output_queue: Optional[ap.AioQueue]=None):
        super(TonlibWorker, self).__init__()

        self.input_queue = input_queue or ap.AioQueue()
        self.output_queue = output_queue or ap.AioQueue()

        self.ls_index = ls_index
        self.tonlib_settings = tonlib_settings

        self.last_block = -1
        self.is_archival = False
        self.semaphore = None
        self.loop = None
        self.tasks = {}
        self.tonlib = None
        self.is_dead = False

    def run(self):
        policy = asyncio.get_event_loop_policy()
        policy.set_event_loop(policy.new_event_loop())
        self.loop = asyncio.new_event_loop()

        # init tonlib
        self.tonlib = TonlibClient(ls_index=self.ls_index,
                                   config=self.tonlib_settings.liteserver_config,
                                   keystore=self.tonlib_settings.keystore,
                                   loop=self.loop,
                                   cdll_path=self.tonlib_settings.cdll_path)
        self.loop.run_until_complete(self.tonlib.init())

        # creating tasks
        self.tasks['report_last_block'] = self.loop.create_task(self.report_last_block())
        self.tasks['report_archival'] = self.loop.create_task(self.report_archival())
        self.tasks['main_loop'] = self.loop.create_task(self.main_loop())
        self.loop.run_until_complete(self.idle_loop())

    @property
    def info(self):
        return {
            'ip': f"{self.tonlib_settings.liteserver_config['liteservers'][0]['ip']}",
            'port': f"{self.tonlib_settings.liteserver_config['liteservers'][0]['port']}",
            'last_block': self.last_block,
            'archival': self.is_archival,
            'number': self.ls_index,
        }

    async def report_dead(self):
        if not self.is_dead:
            self.is_dead = True

            format_exc = traceback.format_exc()
            logger.info(f'Dead report: {format_exc}')
            await self.output_queue.coro_put((TonlibWorkerMsgType.DEAD_REPORT, format_exc))

    async def report_last_block(self):
        try:
            while not self.is_dead:
                last_block = -1
                try:
                    masterchain_info = await self.tonlib.get_masterchain_info()
                    last_block = masterchain_info["last"]["seqno"]
                except Exception as e:
                    logger.error(f"Client #{self.ls_index:03d} report_last_block exception: {e}")
                self.last_block = last_block
                await self.output_queue.coro_put((TonlibWorkerMsgType.LAST_BLOCK_UPDATE, self.last_block))
                await asyncio.sleep(1)
        except:
            await self.report_dead()

    async def report_archival(self):
        try:
            while not self.is_dead:
                is_archival = False
                try:
                    block_transactions = await self.tonlib.get_block_transactions(-1, -9223372036854775808, random.randint(2, 2000000), count=10)
                    is_archival = block_transactions.get("@type", "") == "blocks.transactions"
                except Exception as e:
                    logger.error(f"Client #{self.ls_index:03d} report_archival exception {e}")
                self.is_archival = is_archival
                await self.output_queue.coro_put((TonlibWorkerMsgType.ARCHIVAL_UPDATE, self.is_archival))
                await asyncio.sleep(600)
        except:
            await self.report_dead()
        
    async def main_loop(self):
        try:
            while not self.is_dead:
                try:
                    task_id, timeout, method, args, kwargs = await self.input_queue.coro_get(timeout=3)
                except:
                    continue

                result = None
                exception = None

                start_time = datetime.now()
                if time.time() < timeout:
                    try:
                        result = await self.tonlib.__getattribute__(method)(*args, **kwargs)
                    except asyncio.CancelledError:
                        exception = Exception("Liteserver timeout")
                        logger.warning(f"Client #{self.ls_index:03d} did not get response from liteserver before timeout")
                    except Exception as e:
                        exception = e
                        logger.warning(f"Client #{self.ls_index:03d} raised exception {e} while executing task")
                    else:
                        logger.debug(f"Client #{self.ls_index:03d} got result {method}")
                else:
                    exception = asyncio.TimeoutError()
                    logger.warning(f"Client #{self.ls_index:03d} received task after timeout")
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
                await self.output_queue.coro_put((TonlibWorkerMsgType.TASK_RESULT, tonlib_task_result))
        except:
            await self.report_dead()
        
    async def idle_loop(self):
        while not self.is_dead:
            await asyncio.sleep(0.5)
