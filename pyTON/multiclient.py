import random
import inspect
import asyncio
import copy
import time
import codecs
import traceback

from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict

import aioprocessing

from config import settings
from pyTON.utils import TonLibWrongResult, b64str_to_hex, hash_to_hex
from pyTON.logging import to_mongodb
from pyTON.cache import redis_cached
from pyTON.dispatcher import Dispatcher
from pyTON.client import TonlibClient
from tvm_valuetypes import deserialize_boc

from loguru import logger


def current_function_name():
    return inspect.stack()[1].function


class TonlibClientResult:
    def __init__(self, 
                 task_id, 
                 method: str,
                 elapsed_time: float,
                 params: Optional[Any]=None,
                 result: Optional[Any]=None, 
                 exception: Optional[Exception]=None, 
                 liteserver_info: Optional[Any]=None):
        if result is None and exception is None:
            raise ValueError("TonlibClientResult: both result and exception is None")

        self.task_id = task_id
        self.method = method
        self.elapsed_time = elapsed_time
        self.params = params
        self.result = result
        self.exception = exception
        self.liteserver_info = liteserver_info


@to_mongodb('liteserver_tasks')
def log_liteserver_task(task_result: TonlibClientResult):
    res_type = task_result.result.get('@type', 'unknown') if task_result.result else 'error'
    details = {}
    if res_type == 'error' or res_type == 'unknown':
        details['params'] = task_result.params
        details['result'] = task_result.result
        details['exception'] = str(task_result.exception)
    
    return {
        'timestamp': datetime.utcnow(),
        'elapsed': task_result.elapsed_time,
        'task_id': task_result.task_id,
        'method': task_result.method,
        'liteserver_info': task_result.liteserver_info,
        'result_type': res_type,
        'details': details,
    }


class TonlibMultiClient:
    def __init__(self, 
                 loop, 
                 config: Dict[str, Any], 
                 keystore: str, 
                 dispatcher: Optional[Dispatcher]=None, 
                 cdll_path: Optional[str]=None):
        self.loop = loop
        self.config = config
        self.futures = {}
        self.keystore = keystore
        self.cdll_path = cdll_path

        self.dispatcher = dispatcher or Dispatcher(len(config['liteservers']))
        self.current_consensus_block = 0
        self.current_consensus_block_timestamp = 0

    def init_tonlib(self):
        '''
          Try to init as many tonlib clients as there are liteservers in config
        '''
        self.all_clients = []
        init_task_list = []
        for i, ls in enumerate(self.config["liteservers"]):
            c = copy.deepcopy(self.config)
            c["liteservers"] = [ls]
            keystore = self.keystore + str(i)

            Path(keystore).mkdir(parents=True, exist_ok=True)

            client = TonlibClient(self.loop, i, c, keystore=keystore, cdll_path=self.cdll_path)
            asyncio.ensure_future(client.init_tonlib(), loop=self.loop)
            self.all_clients.append(client)

    # Used by ring library. Since we need shared cache across
    # multiple TonlibMultiClient instances this function must
    # return some static value.
    def __ring_key__(self):
        return "static"


    async def dispatch_request(self, method, archival, *args, **kwargs):
        client_idx = self.dispatcher.getLiteServerIndex(archival)
        client = self.all_clients[client_idx]

        result = None
        exception = None

        start_time = datetime.now()
        try:
            result = await asyncio.wait_for(client.__getattribute__(method)(*args, **kwargs), timeout=settings.pyton.request_timeout)
        except asyncio.CancelledError:
            exception = Exception('Liteserver timeout (cancelled)')
            logger.warning(f"Client #{client_idx:03d} did not get response from liteserver before timeout")
        except asyncio.TimeoutError:
            exception = Exception("Liteserver timeout (asyncio)")
            logger.warning(f"Client #{client_idx:03d} task timeout")
        except Exception as e:
            exception = e
            logger.warning(f"Client #{client_idx:03d} raised exception {e} while executing task")
        else:
            logger.info(f"Client #{client_idx:03d} got result {method}")

        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        # result
        tonlib_task_result = TonlibClientResult('?',
                                                method,
                                                elapsed_time=elapsed_time,
                                                params=[args, kwargs],
                                                result=result,
                                                exception=exception,
                                                liteserver_info=client.info)
        logger.debug(f"Client #{client_idx:03d}, result: {result}, exception: {exception}")

        # logging
        log_liteserver_task(tonlib_task_result)

        # return results
        if exception is not None:
            raise exception

        return result

    @redis_cached(expire=5)
    async def raw_get_transactions(self, account_address: str, from_transaction_lt: str, from_transaction_hash: str, archival: bool):
        if archival:
            return await self.dispatch_request(current_function_name(), True, account_address, from_transaction_lt, from_transaction_hash)
        else:
            return await self.dispatch_request(current_function_name(), False, account_address, from_transaction_lt, from_transaction_hash)

    @redis_cached(expire=15, check_error=False)
    async def get_transactions(self, account_address, from_transaction_lt=None, from_transaction_hash=None, to_transaction_lt=0, limit=10, archival=False):
        """
         Return all transactions between from_transaction_lt and to_transaction_lt
         if to_transaction_lt and to_transaction_hash are not defined returns all transactions
         if from_transaction_lt and from_transaction_hash are not defined latest transactions are returned
        """
        if from_transaction_hash:
            from_transaction_hash = hash_to_hex(from_transaction_hash)
        if (from_transaction_lt == None) or (from_transaction_hash == None):
            addr = await self.raw_get_account_state(account_address)
            try:
                from_transaction_lt, from_transaction_hash = int(addr["last_transaction_id"]["lt"]), b64str_to_hex(addr["last_transaction_id"]["hash"])
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
                current_lt, curret_hash = int(next["lt"]), b64str_to_hex(next["hash"])
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
        return all_transactions[:limit]

    @redis_cached(expire=5)
    async def raw_get_account_state(self, address: str):
        addr = await self.dispatch_request(current_function_name(), False, address)
        # FIXME: refactor this code
        if addr.get('@type','error') == 'error':
            addr = await self.dispatch_request(current_function_name(), False, address)
        if addr.get('@type','error') == 'error':
            raise TonLibWrongResult("raw.getAccountState failed", addr)
        return addr

    @redis_cached(expire=5)
    async def generic_get_account_state(self, address: str):
        return await self.dispatch_request(current_function_name(), False, address)

    @redis_cached(expire=5)
    async def raw_run_method(self, address, method, stack_data, output_layout=None):
        return await self.dispatch_request(current_function_name(), False, address, method, stack_data, output_layout)

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
        return await self.dispatch_request(current_function_name(), False, destination, body, init_code, init_data)

    async def _raw_send_query(self, query_info):
        return await self.dispatch_request(current_function_name(), query_info)

    async def raw_create_and_send_query(self, destination, body, init_code=b'', init_data=b''):
        return await self.dispatch_request(current_function_name(), False, destination, body, init_code, init_data)

    async def raw_create_and_send_message(self, destination, body, initial_account_state=b''):
        return await self.dispatch_request(current_function_name(), False, destination, body, initial_account_state)

    @redis_cached(expire=5)
    async def raw_estimate_fees(self, destination, body, init_code=b'', init_data=b'', ignore_chksig=True):
        return await self.dispatch_request(current_function_name(), False, destination, body, init_code, init_data, ignore_chksig)

    @redis_cached(expire=1)
    async def getMasterchainInfo(self):
        return await self.dispatch_request(current_function_name(), False)

    async def getConsensusBlock(self):
        return {
            "consensus_block": self.current_consensus_block,
            "timestamp": self.current_consensus_block_timestamp
        }

    @redis_cached(expire=600)
    async def lookupBlock(self, workchain, shard, seqno=None, lt=None, unixtime=None):
        if workchain == -1 and seqno and self.current_consensus_block - seqno < 2000:
            return await self.dispatch_request(current_function_name(), False, workchain, shard, seqno, lt, unixtime)
        else:
            return await self.dispatch_request(current_function_name(), True, workchain, shard, seqno, lt, unixtime)

    @redis_cached(expire=600)
    async def getShards(self, master_seqno=None, lt=None, unixtime=None):
        if master_seqno and self.current_consensus_block - master_seqno < 2000:
            return await self.dispatch_request(current_function_name(), False, master_seqno)
        else:
            return await self.dispatch_request(current_function_name(), True, master_seqno)

    @redis_cached(expire=600)
    async def raw_getBlockTransactions(self, fullblock, count, after_tx):
        return await self.dispatch_request(current_function_name(), True, fullblock, count, after_tx)

    @redis_cached(expire=600)
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
                tx["account"] = "%d:%s" % (result["id"]["workchain"], b64str_to_hex(tx["account"]))
            except:
                pass
        return total_result

    @redis_cached(expire=600)
    async def getBlockHeader(self, workchain, shard, seqno, root_hash=None, file_hash=None):
        if workchain == -1 and seqno and self.current_consensus_block - seqno < 2000:
            return await self.dispatch_request(current_function_name(), False, workchain, shard, seqno, root_hash, file_hash)
        else:
            return await self.dispatch_request(current_function_name(), True, workchain, shard, seqno, root_hash, file_hash)

    @redis_cached(expire=600, check_error=False)
    async def tryLocateTxByOutcomingMessage(self, source, destination, creation_lt):
        return await self.dispatch_request(current_function_name(), True, source, destination, creation_lt)

    @redis_cached(expire=600, check_error=False)
    async def tryLocateTxByIncomingMessage(self, source, destination, creation_lt):
        return await self.dispatch_request(current_function_name(), True, source, destination, creation_lt)
