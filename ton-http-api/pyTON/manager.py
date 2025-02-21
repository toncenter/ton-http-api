import asyncio
import time
import traceback
import random
import queue

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

from pyTON.worker import TonlibWorker
from pyTON.models import TonlibWorkerMsgType, TonlibClientResult, ConsensusBlock
from pyTON.cache import CacheManager, DisabledCacheManager
from pyTON.settings import TonlibSettings

from pytonlib import TonlibError

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from loguru import logger


class TonlibManager:
    def __init__(self,
                 tonlib_settings: TonlibSettings,
                 dispatcher: Optional["Dispatcher"]=None,
                 cache_manager: Optional["CacheManager"]=None,
                 loop: Optional[asyncio.BaseEventLoop]=None):
        self.tonlib_settings = tonlib_settings
        self.dispatcher = dispatcher
        self.cache_manager = cache_manager or DisabledCacheManager()

        self.workers = {}
        self.futures = {}
        self.tasks = {}
        self.consensus_block = ConsensusBlock()

        # cache setup
        self.setup_cache()

        self.threadpool_executor = ThreadPoolExecutor(max_workers=max(32, len(self.tonlib_settings.liteserver_config['liteservers']) * 4))

        # workers spawn
        self.loop = loop or asyncio.get_running_loop()
        for ls_index in range(len(self.tonlib_settings.liteserver_config['liteservers'])):
            self.spawn_worker(ls_index)

        # running tasks
        self.tasks['check_working'] = self.loop.create_task(self.check_working())
        self.tasks['check_children_alive'] = self.loop.create_task(self.check_children_alive())

    async def shutdown(self):
        for i in self.futures:
            self.futures[i].cancel()
        
        self.tasks['check_working'].cancel()
        await self.tasks['check_working']
        
        self.tasks['check_children_alive'].cancel()
        await self.tasks['check_children_alive']

        await asyncio.wait([self.loop.create_task(self.worker_control(i, enabled=False)) for i in self.workers])

        self.threadpool_executor.shutdown()

    def setup_cache(self):
        self.raw_get_transactions = self.cache_manager.cached(expire=5)(self.raw_get_transactions)
        self.get_transactions = self.cache_manager.cached(expire=15, check_error=False)(self.get_transactions)
        self.raw_get_account_state = self.cache_manager.cached(expire=5)(self.raw_get_account_state)
        self.generic_get_account_state = self.cache_manager.cached(expire=5)(self.generic_get_account_state)
        self.raw_run_method = self.cache_manager.cached(expire=5)(self.raw_run_method)
        self.raw_estimate_fees = self.cache_manager.cached(expire=5)(self.raw_estimate_fees)
        self.getMasterchainInfo = self.cache_manager.cached(expire=1)(self.getMasterchainInfo)
        self.getMasterchainBlockSignatures = self.cache_manager.cached(expire=5)(self.getMasterchainBlockSignatures)
        self.getShardBlockProof = self.cache_manager.cached(expire=5)(self.getShardBlockProof)
        self.lookupBlock = self.cache_manager.cached(expire=600)(self.lookupBlock)
        self.getShards = self.cache_manager.cached(expire=600)(self.getShards)
        self.raw_getBlockTransactions = self.cache_manager.cached(expire=600)(self.raw_getBlockTransactions)
        self.getBlockTransactions = self.cache_manager.cached(expire=600)(self.getBlockTransactions)
        self.getBlockHeader = self.cache_manager.cached(expire=600)(self.getBlockHeader)
        self.get_config_param = self.cache_manager.cached(expire=5)(self.get_config_param)
        self.get_token_data = self.cache_manager.cached(expire=15)(self.get_token_data)
        self.tryLocateTxByOutcomingMessage = self.cache_manager.cached(expire=600, check_error=False)(self.tryLocateTxByOutcomingMessage)
        self.tryLocateTxByIncomingMessage = self.cache_manager.cached(expire=600, check_error=False)(self.tryLocateTxByIncomingMessage)

    def spawn_worker(self, ls_index, force_restart=False):
        if ls_index in self.workers:
            worker_info = self.workers[ls_index]
            if not force_restart and worker_info.is_alive():
                logger.warning('Worker for liteserver #{ls_index} already exists', ls_index=ls_index)
                return
            try:
                worker_info['reader'].cancel()  
                worker_info['worker'].exit_event.set()
                worker_info['worker'].output_queue.cancel_join_thread()
                worker_info['worker'].input_queue.cancel_join_thread()
                worker_info['worker'].output_queue.close()
                worker_info['worker'].input_queue.close()
                worker_info['worker'].join(timeout=3)
            except Exception as ee:
                logger.error('Failed to delete existing process: {exc}', exc=ee)
        # running new worker
        if not ls_index in self.workers:
            self.workers[ls_index] = {
                'is_working': False,
                'is_enabled': True,
                'restart_count': -1,
                'tasks_count': 0
            }
        
        tonlib_settings = deepcopy(self.tonlib_settings)
        tonlib_settings.keystore += f'worker_{ls_index}'
        self.workers[ls_index]['worker'] = TonlibWorker(ls_index, tonlib_settings)
        self.workers[ls_index]['reader'] = self.loop.create_task(self.read_results(ls_index))
        self.workers[ls_index]['worker'].start()
        self.workers[ls_index]['restart_count'] += 1

    async def worker_control(self, ls_index, enabled):
        if enabled == False:
            self.workers[ls_index]['reader'].cancel()
            self.workers[ls_index]['worker'].exit_event.set()

            self.workers[ls_index]['worker'].output_queue.cancel_join_thread()
            self.workers[ls_index]['worker'].input_queue.cancel_join_thread()
            self.workers[ls_index]['worker'].output_queue.close()
            self.workers[ls_index]['worker'].input_queue.close()

            self.workers[ls_index]['worker'].join()
            
            await self.workers[ls_index]['reader']

        self.workers[ls_index]['is_enabled'] = enabled

    def log_liteserver_task(self, task_result: TonlibClientResult):
        result_type = None
        if isinstance(task_result.result, Mapping):
            result_type = task_result.result.get('@type', 'unknown')
        else:
            result_type = type(task_result.result).__name__
        details = {}
        
        rec = {
            'timestamp': datetime.utcnow(),
            'elapsed': task_result.elapsed_time,
            'task_id': task_result.task_id,
            'method': task_result.method,
            'liteserver_info': task_result.liteserver_info,
            'result_type': result_type,
            'exception': task_result.exception 
        }

        logger.info("Received result of type: {result_type}, method: {method}, task_id: {task_id}", **rec)

    async def read_results(self, ls_index):
        worker = self.workers[ls_index]['worker']
        while True:
            try:
                try:
                    msg_type, msg_content = await self.loop.run_in_executor(self.threadpool_executor, worker.output_queue.get, True, 1)
                except queue.Empty:
                    continue
                if msg_type == TonlibWorkerMsgType.TASK_RESULT:
                    task_id = msg_content.task_id

                    if task_id in self.futures and not self.futures[task_id].done():
                        if msg_content.exception is not None:
                            self.futures[task_id].set_exception(msg_content.exception)
                        if msg_content.result is not None:    
                            self.futures[task_id].set_result(msg_content.result)
                    else:
                        logger.warning("TonlibManager received result from TonlibWorker #{ls_index:03d} whose task '{task_id}' doesn't exist or is done.", ls_index=ls_index, task_id=task_id)

                    self.log_liteserver_task(msg_content)

                if msg_type == TonlibWorkerMsgType.LAST_BLOCK_UPDATE:
                    worker.last_block = msg_content

                if msg_type == TonlibWorkerMsgType.ARCHIVAL_UPDATE:
                    worker.is_archival = msg_content
            except asyncio.CancelledError:
                logger.info("Task read_results from TonlibWorker #{ls_index:03d} was cancelled", ls_index=ls_index)
                return
            except:
                logger.error("read_results exception {format_exc}", format_exc=traceback.format_exc())
        
    async def check_working(self):
        while True:
            try:
                last_blocks = [self.workers[ls_index]['worker'].last_block for ls_index in self.workers]
                best_block = max([i for i in last_blocks])
                consensus_block_seqno = 0
                # detect 'consensus':
                # it is no more than 3 blocks less than best block
                # at least 60% of ls know it
                # it is not earlier than prev
                last_blocks_non_zero = [i for i in last_blocks if i != 0]
                strats = [sum([1 if ls == (best_block-i) else 0 for ls in last_blocks_non_zero]) for i in range(4)]
                total_suitable = sum(strats)
                sm = 0
                for i, am in enumerate(strats):
                    sm += am
                    if sm >= total_suitable * 0.6:
                        consensus_block_seqno = best_block - i
                        break
                if consensus_block_seqno > self.consensus_block.seqno:
                    self.consensus_block.seqno = consensus_block_seqno
                    self.consensus_block.timestamp = datetime.utcnow().timestamp()
                for ls_index in self.workers:
                    self.workers[ls_index]['is_working'] = last_blocks[ls_index] >= self.consensus_block.seqno

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info('Task check_working was cancelled')
                return
            except:
                logger.critical('Task check_working dead: {format_exc}', format_exc=traceback.format_exc())

    async def check_children_alive(self):
        while True:
            try:
                for ls_index in self.workers:
                    worker_info = self.workers[ls_index]
                    worker_info['is_enabled'] = worker_info['is_enabled'] or time.time() > worker_info.get('time_to_alive', 1e10)
                    if worker_info['restart_count'] >= 3:
                        worker_info['is_enabled'] = False
                        worker_info['time_to_alive'] = time.time() + 10 * 60
                        worker_info['restart_count'] = 0
                    if not worker_info['worker'].is_alive() and worker_info['is_enabled']:
                        logger.error("TonlibWorker #{ls_index:03d} is dead!!! Exit code: {exit_code}", ls_index=ls_index, exit_code=self.workers[ls_index]['worker'].exitcode)
                        self.spawn_worker(ls_index, force_restart=True)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info('Task check_children_alive was cancelled')
                return
            except:
                logger.critical('Task check_children_alive dead: {format_exc}', format_exc=traceback.format_exc())

    def get_workers_state(self):
        result = {}
        for ls_index, worker_info in self.workers.items():
            result[ls_index] = {
                'ls_index': ls_index,
                **self.tonlib_settings.liteserver_config['liteservers'][ls_index],
                'is_working': worker_info['is_working'],
                'is_archival': worker_info['worker'].is_archival,
                'is_enabled': worker_info['is_enabled'],
                'last_block': worker_info['worker'].last_block,
                'restart_count': worker_info['restart_count'],
                'tasks_count': worker_info['tasks_count']
            }
        return result

    def select_worker(self, ls_index=None, archival=None, count=1):
        if count == 1 and ls_index is not None and self.workers[ls_index]['is_working']:
            return ls_index 

        suitable = [ls_index for ls_index, worker_info in self.workers.items() if worker_info['is_working'] and 
                    (archival is None or worker_info['worker'].is_archival == archival)]
        random.shuffle(suitable)
        if len(suitable) < count:
            logger.warning('Required number of workers is not reached: found {found} of {count}', found=len(suitable), count=count)
        if len(suitable) == 0:
            raise RuntimeError(f'No working liteservers with ls_index={ls_index}, archival={archival}')
        return suitable[:count] if count > 1 else suitable[0]

    async def dispatch_request_to_worker(self, method, ls_index, *args, **kwargs):
        task_id = "{}:{}".format(time.time(), random.random())
        timeout = time.time() + self.tonlib_settings.request_timeout
        self.workers[ls_index]['tasks_count'] += 1

        logger.info("Sending request method: {method}, task_id: {task_id}, ls_index: {ls_index}", 
            method=method, task_id=task_id, ls_index=ls_index)
        await self.loop.run_in_executor(self.threadpool_executor, self.workers[ls_index]['worker'].input_queue.put, (task_id, timeout, method, args, kwargs))

        try:
            self.futures[task_id] = self.loop.create_future()
            await self.futures[task_id]
            return self.futures[task_id].result()
        finally:
            self.futures.pop(task_id)

    def dispatch_request(self, method, *args, **kwargs):
        ls_index = self.select_worker()
        return self.dispatch_request_to_worker(method, ls_index, *args, **kwargs)

    def dispatch_archival_request(self, method, *args, **kwargs):
        ls_index = None
        try:
            ls_index = self.select_worker(archival=True)
        except RuntimeError as ee:
            logger.warning(f'Method {method} failed to execute on archival node: {ee}')
            ls_index = self.select_worker(archival=False)
        return self.dispatch_request_to_worker(method, ls_index, *args, **kwargs)

    async def raw_get_transactions(self, account_address: str, from_transaction_lt: str, from_transaction_hash: str, archival: bool):
        method = 'raw_get_transactions'
        if archival:
            return await self.dispatch_archival_request(method, account_address, from_transaction_lt, from_transaction_hash)
        else:
            return await self.dispatch_request(method, account_address, from_transaction_lt, from_transaction_hash)

    async def get_transactions(self, account_address, from_transaction_lt=None, from_transaction_hash=None, to_transaction_lt=0, limit=10, decode_messages=True, archival=False):
        """
         Return all transactions between from_transaction_lt and to_transaction_lt
         if to_transaction_lt and to_transaction_hash are not defined returns all transactions
         if from_transaction_lt and from_transaction_hash are not defined latest transactions are returned
        """
        method = 'get_transactions'
        if archival:
            return await self.dispatch_archival_request(method, account_address, from_transaction_lt, from_transaction_hash, to_transaction_lt, limit, decode_messages)
        else:
            return await self.dispatch_request(method, account_address, from_transaction_lt, from_transaction_hash, to_transaction_lt, limit, decode_messages)

    async def raw_get_account_state(self, address: str, seqno: int = None):
        method = 'raw_get_account_state'
        try:
            addr = await self.dispatch_request(method, address, seqno)
        except TonlibError:
            addr = await self.dispatch_archival_request(method, address, seqno)
        return addr

    async def generic_get_account_state(self, address: str, seqno: int = None):
        method = 'generic_get_account_state'
        try:
            addr = await self.dispatch_request(method, address, seqno)
        except TonlibError:
            addr = await self.dispatch_archival_request(method, address, seqno)
        return addr

    async def get_token_data(self, address: str):
        return await self.dispatch_request('get_token_data', address)

    async def raw_run_method(self, address, method, stack_data, seqno):
        try:
            return await self.dispatch_request('raw_run_method', address, method, stack_data, seqno)
        except TonlibError:
            return await self.dispatch_archival_request('raw_run_method', address, method, stack_data, seqno)

    async def _send_message(self, serialized_boc, method):
        ls_index_list = self.select_worker(count=4)
        result = None
        try:
            task_ids = []
            for ls_index in ls_index_list:
                task_id = "{}:{}".format(time.time(), random.random())
                timeout = time.time() + self.tonlib_settings.request_timeout
                await self.loop.run_in_executor(self.threadpool_executor, self.workers[ls_index]['worker'].input_queue.put, (task_id, timeout, method, [serialized_boc], {}))

                self.futures[task_id] = self.loop.create_future()
                task_ids.append(task_id)

            done, _ = await asyncio.wait([self.futures[task_id] for task_id in task_ids], return_when=asyncio.FIRST_COMPLETED)
            result = list(done)[0].result()
        finally:
            for task_id in task_ids:
                self.futures.pop(task_id)

        return result

    async def raw_send_message(self, serialized_boc):
        return await self._send_message(serialized_boc, 'raw_send_message')

    async def raw_send_message_return_hash(self, serialized_boc):
        return await self._send_message(serialized_boc, 'raw_send_message_return_hash')

    async def _raw_create_query(self, destination, body, init_code=b'', init_data=b''):
        return await self.dispatch_request('_raw_create_query', destination, body, init_code, init_data)

    async def _raw_send_query(self, query_info):
        return await self.dispatch_request('_raw_send_query', query_info)

    async def raw_create_and_send_query(self, destination, body, init_code=b'', init_data=b''):
        return await self.dispatch_request('raw_create_and_send_query', destination, body, init_code, init_data)

    async def raw_create_and_send_message(self, destination, body, initial_account_state=b''):
        return await self.dispatch_request('raw_create_and_send_message', destination, body, initial_account_state)

    async def raw_estimate_fees(self, destination, body, init_code=b'', init_data=b'', ignore_chksig=True):
        return await self.dispatch_request('raw_estimate_fees', destination, body, init_code, init_data, ignore_chksig)

    async def getMasterchainInfo(self):
        return await self.dispatch_request('get_masterchain_info')

    async def getMasterchainBlockSignatures(self, seqno):
        return await self.dispatch_request('get_masterchain_block_signatures', seqno)
    
    async def getShardBlockProof(self, workchain, shard, seqno, from_seqno):
        return await self.dispatch_request('get_shard_block_proof', workchain, shard, seqno, from_seqno)

    async def getConsensusBlock(self):
        return {
            "consensus_block": self.consensus_block.seqno,
            "timestamp": self.consensus_block.timestamp
        }

    async def lookupBlock(self, workchain, shard, seqno=None, lt=None, unixtime=None):
        method = 'lookup_block'
        if workchain == -1 and seqno and self.consensus_block.seqno - seqno < 2000:
            return await self.dispatch_request(method, workchain, shard, seqno, lt, unixtime)
        else:
            return await self.dispatch_archival_request(method, workchain, shard, seqno, lt, unixtime)

    async def getShards(self, master_seqno=None, lt=None, unixtime=None):
        method = 'get_shards'
        if master_seqno and self.consensus_block.seqno - master_seqno < 2000:
            return await self.dispatch_request(method, master_seqno)
        else:
            return await self.dispatch_archival_request(method, master_seqno)

    async def raw_getBlockTransactions(self, fullblock, count, after_tx):
        return await self.dispatch_archival_request('raw_get_block_transactions', fullblock, count, after_tx)

    async def getBlockTransactions(self, workchain, shard, seqno, count, root_hash=None, file_hash=None, after_lt=None, after_hash=None):
        return await self.dispatch_archival_request('get_block_transactions', workchain, shard, seqno, count, root_hash, file_hash, after_lt, after_hash)

    async def getBlockTransactionsExt(self, workchain, shard, seqno, count, root_hash=None, file_hash=None, after_lt=None, after_hash=None):
        return await self.dispatch_archival_request('get_block_transactions_ext', workchain, shard, seqno, count, root_hash, file_hash, after_lt, after_hash)

    async def getBlockHeader(self, workchain, shard, seqno, root_hash=None, file_hash=None):
        method = 'get_block_header'
        if workchain == -1 and seqno and self.consensus_block.seqno - seqno < 2000:
            return await self.dispatch_request(method, workchain, shard, seqno, root_hash, file_hash)
        else:
            return await self.dispatch_archival_request(method, workchain, shard, seqno, root_hash, file_hash)

    async def get_config_param(self, config_id: int, seqno: Optional[int]):
        seqno = seqno or self.consensus_block.seqno
        method = 'get_config_param'
        if self.consensus_block.seqno - seqno < 2000:
            return await self.dispatch_request(method, config_id, seqno)
        else:
            return await self.dispatch_archival_request(method, config_id, seqno)

    async def tryLocateTxByOutcomingMessage(self, source, destination, creation_lt):
        return await self.dispatch_archival_request('try_locate_tx_by_outcoming_message',  source, destination, creation_lt)

    async def tryLocateTxByIncomingMessage(self, source, destination, creation_lt):
        return await self.dispatch_archival_request('try_locate_tx_by_incoming_message',  source, destination, creation_lt)
