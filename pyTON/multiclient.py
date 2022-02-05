import random
import inspect
import asyncio
import copy
import time
import codecs
import struct
import socket
import threading
import aioprocessing
import traceback
import json
import aiocache

from pathlib import Path
from aiocache import cached, Cache, AIOCACHE_CACHES
from aiocache.serializers import PickleSerializer
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from config import settings
from pyTON.tonlibjson import TonLib
from pyTON.address_utils import prepare_address, detect_address
from pyTON.utils import TonLibWrongResult
from pyTON.logging import to_mongodb
from pyTON.client import TonlibClient, TonlibClientResult, MsgType, b64str_bytes, b64str_str, b64str_hex, h2b64
from tvm_valuetypes import serialize_tvm_stack, render_tvm_stack, deserialize_boc

from loguru import logger


def current_function_name():
    return inspect.stack()[1].function


def log_liteserver_task(task_result: TonlibClientResult, postgres: ):
    res_type = task_result.result.get('@type', 'unknown') if task_result.result else 'error'
    details = {}
    if res_type == 'error' or res_type == 'unknown':
        details['params'] = task_result.params
        details['result'] = task_result.result
        details['exception'] = str(task_result.exception)
    
    record = {
        'timestamp': datetime.utcnow(),
        'elapsed': task_result.elapsed_time,
        'task_id': task_result.task_id,
        'method': task_result.method,
        'liteserver_info': task_result.liteserver_info,
        'result_type': res_type,
        'details': json.dumps(details),
    }



class TonlibMultiClient:
    def __init__(self, loop, config, keystore, cdll_path=None):
        self.loop = loop
        self.config = config
        self.futures = {}
        self.keystore = keystore
        self.cdll_path = cdll_path
        self.current_consensus_block = 0
        self.current_consensus_block_timestamp = 0

    def init_tonlib(self):
        '''
          Try to init as many tonlib clients as there are liteservers in config
        '''
        self.all_clients = []
        self.read_output_tasks = []
        for i, ls in enumerate(self.config["liteservers"]):
            c = copy.deepcopy(self.config)
            c["liteservers"] = [ls]
            keystore = self.keystore + str(i)

            Path(keystore).mkdir(parents=True, exist_ok=True)

            client = TonlibClient(aioprocessing.AioQueue(), aioprocessing.AioQueue(), c, keystore=keystore, cdll_path=self.cdll_path)

            client.number = i
            client.is_working = False
            client.is_archival = False

            client.start()

            self.all_clients.append(client)
            self.read_output_tasks.append(asyncio.ensure_future(self.read_output(client), loop=self.loop))

        self.check_working_task = asyncio.ensure_future(self.check_working(), loop=self.loop)
        self.check_children_alive_task = asyncio.ensure_future(self.check_children_alive(), loop=self.loop)

    async def read_output(self, client):
        while True:
            try:
                msg_type, msg_content = await client.output_queue.coro_get()
                if msg_type == MsgType.TASK_RESULT:
                    task_id = msg_content.task_id
                    result = msg_content.result
                    exception = msg_content.exception
                    if task_id in self.futures and not self.futures[task_id].done():
                        if exception is not None:
                            self.futures[task_id].set_exception(exception)
                        if result is not None:    
                            self.futures[task_id].set_result(result)
                        logger.debug(f"Client #{client.number:03d}, task '{task_id}' result: {result}, exception: {exception}")
                        
                        # log liteserver task
                        log_liteserver_task(msg_content)
                    else:
                        logger.warning(f"Client #{client.number:03d}, task '{task_id}' doesn't exist or is done.")

                if msg_type == MsgType.LAST_BLOCK_UPDATE:
                    client.last_block = msg_content

                if msg_type == MsgType.ARCHIVAL_UPDATE:
                    client.is_archival = msg_content
            except Exception as e:
                logger.error(f"read_output exception {traceback.format_exc()}")

    async def check_working(self):
        while True:
            last_blocks = [client.last_block for client in self.all_clients]
            best_block = max([i for i in last_blocks])
            consensus_block = 0
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
                    consensus_block = best_block - i
                    break
            if consensus_block > self.current_consensus_block:
                self.current_consensus_block = consensus_block
                self.current_consensus_block_timestamp = datetime.utcnow().timestamp()
            for i in range(len(self.all_clients)):
                self.all_clients[i].is_working = last_blocks[i] >= self.current_consensus_block

            await asyncio.sleep(1)

    async def check_children_alive(self):
        while True:
            for i, client in enumerate(self.all_clients):
                if not client.is_alive():
                    logger.error(f"Client #{i:03d} dead!!! Exit code: {client.exitcode}")

                    self.read_output_tasks[i].cancel()
                    client.close()

                    c = copy.deepcopy(self.config)
                    c["liteservers"] = [self.config["liteservers"][i]]
                    keystore = self.keystore + str(i)
                    new_client = TonlibClient(aioprocessing.AioQueue(), aioprocessing.AioQueue(), c, keystore=keystore, cdll_path=self.cdll_path)
                    
                    # lite server info
                    new_client.number = i
                    new_client.is_working = False
                    new_client.is_archival = False
                    new_client.start()
                    self.all_clients[i] = new_client

                    self.read_output_tasks[i] = asyncio.ensure_future(self.read_output(new_client), loop=self.loop)

            await asyncio.sleep(1)

    async def _dispatch_request_to_liteserver(self, method, client, *args, **kwargs):
        task_id = "{}:{}".format(time.time(), random.random())
        timeout = time.time() + settings.pyton.request_timeout
        await client.input_queue.coro_put((task_id, timeout, method, args, kwargs))

        try:
            self.futures[task_id] = self.loop.create_future()
            await self.futures[task_id]
            return self.futures[task_id].result()
        finally:
            self.futures.pop(task_id)

    async def dispatch_request(self, method, *args, **kwargs):
        client = random.choice([cl for cl in self.all_clients if cl.is_working])
        result = await self._dispatch_request_to_liteserver(method, client, *args, **kwargs)
        return result

    async def dispatch_archive_request(self, method, *args, **kwargs):
        clnts = [cl for cl in self.all_clients if cl.is_working and cl.is_archival]
        if not len(clnts):
            clnts = [cl for cl in self.all_clients if cl.is_working]
        client = random.choice(clnts)
        result = await self._dispatch_request_to_liteserver(method, client, *args, **kwargs)
        return result

    @cached(ttl=5, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def raw_get_transactions(self, account_address: str, from_transaction_lt: str, from_transaction_hash: str, archival: bool):
        if archival:
            return await self.dispatch_archive_request(current_function_name(), account_address, from_transaction_lt, from_transaction_hash)
        else:
            return await self.dispatch_request(current_function_name(), account_address, from_transaction_lt, from_transaction_hash)

    @cached(ttl=15, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def get_transactions(self, account_address, from_transaction_lt=None, from_transaction_hash=None, to_transaction_lt=0, limit=10, archival=False):
        """
         Return all transactions between from_transaction_lt and to_transaction_lt
         if to_transaction_lt and to_transaction_hash are not defined returns all transactions
         if from_transaction_lt and from_transaction_hash are not defined checks last
        """
        if (from_transaction_lt == None) or (from_transaction_hash == None):
            addr = await self.raw_get_account_state(account_address)
            try:
                from_transaction_lt, from_transaction_hash = int(addr["last_transaction_id"]["lt"]), b64str_hex(addr["last_transaction_id"]["hash"])
            except KeyError:
                raise TonLibWrongResult("Can't get last_transaction_id data", addr)
        reach_lt = False
        all_transactions = []
        current_lt, curret_hash = from_transaction_lt, from_transaction_hash
        while (not reach_lt) and (len(all_transactions) < limit):
            raw_transactions = await self.raw_get_transactions(account_address, current_lt, curret_hash, archival)
            if(raw_transactions['@type']) == 'error':
                break
                # TODO probably we should chenge get_transactions API
                # if 'message' in raw_transactions['message']:
                #  raise Exception(raw_transactions['message'])
                # else:
                #  raise Exception("Can't get transactions")
            transactions, next = raw_transactions['transactions'], raw_transactions.get("previous_transaction_id", None)
            for t in transactions:
                tlt = int(t['transaction_id']['lt'])
                if tlt <= to_transaction_lt:
                    reach_lt = True
                    break
                all_transactions.append(copy.deepcopy(t))
            if next:
                current_lt, curret_hash = int(next["lt"]), b64str_hex(next["hash"])
            else:
                break
            if current_lt == 0:
                break
        for t in all_transactions:
            try:
                if "in_msg" in t:
                    if "source" in t["in_msg"]:
                        t["in_msg"]["source"] = t["in_msg"]["source"]["account_address"]
                    if "destination" in t["in_msg"]:
                        t["in_msg"]["destination"] = t["in_msg"]["destination"]["account_address"]
                    try:
                        if "msg_data" in t["in_msg"]:
                            dcd = ""
                            if t["in_msg"]["msg_data"]["@type"] == "msg.dataRaw":
                                msg_cell_boc = codecs.decode(codecs.encode(t["in_msg"]["msg_data"]["body"], 'utf8'), 'base64')
                                message_cell = deserialize_boc(msg_cell_boc)
                                dcd = message_cell.data.data.tobytes()
                                t["in_msg"]["message"] = codecs.decode(codecs.encode(dcd, 'base64'), "utf8")
                            elif t["in_msg"]["msg_data"]["@type"] == "msg.dataText":
                                dcd = codecs.encode(t["in_msg"]["msg_data"]["text"], 'utf8')
                                t["in_msg"]["message"] = codecs.decode(codecs.decode(dcd, 'base64'), "utf8")
                    except Exception as e:
                        t["in_msg"]["message"] = ""
                        print(e)
                if "out_msgs" in t:
                    for o in t["out_msgs"]:
                        if "source" in o:
                            o["source"] = o["source"]["account_address"]
                        if "destination" in o:
                            o["destination"] = o["destination"]["account_address"]
                        try:
                            if "msg_data" in o:
                                dcd = ""
                                if o["msg_data"]["@type"] == "msg.dataRaw":
                                    msg_cell_boc = codecs.decode(codecs.encode(o["msg_data"]["body"], 'utf8'), 'base64')
                                    message_cell = deserialize_boc(msg_cell_boc)
                                    dcd = message_cell.data.data.tobytes()
                                    o["message"] = codecs.decode(codecs.encode(dcd, 'base64'), "utf8")
                                elif o["msg_data"]["@type"] == "msg.dataText":
                                    dcd = codecs.encode(o["msg_data"]["text"], 'utf8')
                                    o["message"] = codecs.decode(codecs.decode(dcd, 'base64'), "utf8")
                        except Exception as e:
                            o["message"] = ""
            except Exception as e:
                print("getTransaction exception", e)
        return all_transactions

    @cached(ttl=5, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def raw_get_account_state(self, address: str):
        addr = await self.dispatch_request(current_function_name(), address)
        # FIXME: refactor this code
        if addr.get('@type','error') == 'error':
            addr = await self.dispatch_request(current_function_name(), address)
        if addr.get('@type','error') == 'error':
            raise TonLibWrongResult("raw.getAccountState failed", addr)
        return addr

    @cached(ttl=5, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def generic_get_account_state(self, address: str):
        return await self.dispatch_request(current_function_name(), address)

    @cached(ttl=5, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def raw_run_method(self, address, method, stack_data, output_layout=None):
        return await self.dispatch_request(current_function_name(), address, method, stack_data, output_layout)

    async def raw_send_message(self, serialized_boc):
        working = [cl for cl in self.all_clients if cl.is_working]
        if len(working) == 0:
            raise Exception("No working liteservers")

        task_ids = []

        result = None
        try:
            for cl in random.sample(working, min(4, len(working))):
                task_id = "{}:{}".format(time.time(), random.random())
                timeout = time.time() + settings.pyton.request_timeout
                await cl.input_queue.coro_put((task_id, timeout, current_function_name(), [serialized_boc], {}))

                self.futures[task_id] = self.loop.create_future()
                task_ids.append(task_id)

            done, pending = await asyncio.wait([self.futures[task_id] for task_id in task_ids], return_when=asyncio.FIRST_COMPLETED)
            result = list(done)[0].result()
        finally:
            for task_id in task_ids:
                self.futures.pop(task_id)

        return result

    async def _raw_create_query(self, destination, body, init_code=b'', init_data=b''):
        return await self.dispatch_request(current_function_name(), destination, body, init_code, init_data)

    async def _raw_send_query(self, query_info):
        return await self.dispatch_request(current_function_name(), query_info)

    async def raw_create_and_send_query(self, destination, body, init_code=b'', init_data=b''):
        return await self.dispatch_request(current_function_name(), destination, body, init_code, init_data)

    async def raw_create_and_send_message(self, destination, body, initial_account_state=b''):
        return await self.dispatch_request(current_function_name(), destination, body, initial_account_state)

    @cached(ttl=5, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def raw_estimate_fees(self, destination, body, init_code=b'', init_data=b'', ignore_chksig=True):
        return await self.dispatch_request(current_function_name(), destination, body, init_code, init_data, ignore_chksig)

    @cached(ttl=1, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def getMasterchainInfo(self):
        return await self.dispatch_request(current_function_name())

    async def getConsensusBlock(self):
        return {
            "consensus_block": self.current_consensus_block,
            "timestamp": self.current_consensus_block_timestamp
        }

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def lookupBlock(self, workchain, shard, seqno=None, lt=None, unixtime=None):
        if workchain == -1 and seqno and self.current_consensus_block - seqno < 2000:
            return await self.dispatch_request(current_function_name(), workchain, shard, seqno, lt, unixtime)
        else:
            return await self.dispatch_archive_request(current_function_name(), workchain, shard, seqno, lt, unixtime)

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def getShards(self, master_seqno=None, lt=None, unixtime=None):
        if master_seqno and self.current_consensus_block - master_seqno < 2000:
            return await self.dispatch_request(current_function_name(), master_seqno)
        else:
            return await self.dispatch_archive_request(current_function_name(), master_seqno)

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def raw_getBlockTransactions(self, fullblock, count, after_tx):
        return await self.dispatch_archive_request(current_function_name(), fullblock, count, after_tx)

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def getBlockTransactions(self, workchain, shard, seqno, count, root_hash=None, file_hash=None, after_lt=None, after_hash=None):
        fullblock = {}
        if root_hash and file_hash:
            fullblock = {
                '@type': 'ton.blockIdExt',
                'workchain': workchain,
                'shard': shard,
                'seqno': seqno,
                'root_hash': root_hash,
                'file_hash': file_hash
            }
        else:
            fullblock = await self.lookupBlock(workchain, shard, seqno)
            if fullblock.get('@type', 'error') == 'error':
                return fullblock
        after_tx = {
            '@type': 'blocks.accountTransactionId',
            'account': after_hash if after_hash else 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
            'lt': after_lt if after_lt else 0
        }
        total_result = None
        incomplete = True
        while incomplete:
            result = await self.raw_getBlockTransactions(fullblock, count, after_tx)
            if(result['@type']) == 'error':
                result = await self.raw_getBlockTransactions(fullblock, count, after_tx)
            if(result['@type']) == 'error':
                raise TonLibWrongResult('Can\'t get blockTransactions', result)
            if not total_result:
                total_result = result
            else:
                total_result["transactions"] += result["transactions"]
                total_result["incomplete"] = result.get("incomplete", False)
            incomplete = result.get("incomplete", False)
            if incomplete:
                after_tx['account'] = result["transactions"][-1]["account"]
                after_tx['lt'] = result["transactions"][-1]["lt"]
        # TODO automatically check incompleteness and download all txes
        for tx in total_result["transactions"]:
            try:
                tx["account"] = "%d:%s" % (result["id"]["workchain"], b64str_hex(tx["account"]))
            except:
                pass
        return total_result

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def getBlockHeader(self, workchain, shard, seqno, root_hash=None, file_hash=None):
        if workchain == -1 and seqno and self.current_consensus_block - seqno < 2000:
            return await self.dispatch_request(current_function_name(), workchain, shard, seqno, root_hash, file_hash)
        else:
            return await self.dispatch_archive_request(current_function_name(), workchain, shard, seqno, root_hash, file_hash)

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def tryLocateTxByOutcomingMessage(self, source, destination, creation_lt):
        return await self.dispatch_archive_request(current_function_name(),  source, destination, creation_lt)

    @cached(ttl=600, cache=Cache.REDIS, **settings.cache_redis, serializer=PickleSerializer())
    async def tryLocateTxByIncomingMessage(self, source, destination, creation_lt):
        return await self.dispatch_archive_request(current_function_name(),  source, destination, creation_lt)
