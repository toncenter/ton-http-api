import json
import platform
import pkg_resources
import random
import asyncio
import time
import functools

from config import settings
from ctypes import *
from loguru import logger
from pyTON.utils import TonLibWrongResult


def get_tonlib_path():
    arch_name = platform.system().lower()
    if arch_name == 'linux':
        lib_name = 'libtonlibjson.so'
    else:
        raise RuntimeError('Platform could not be identified')
    return pkg_resources.resource_filename('pyTON',
                                           'distlib/'+arch_name+'/'+lib_name)


class TonLib:
    def __init__(self, loop, ls_index, cdll_path=None):
        cdll_path = get_tonlib_path() if not cdll_path else cdll_path
        tonlib = CDLL(cdll_path)

        tonlib_json_client_create = tonlib.tonlib_client_json_create
        tonlib_json_client_create.restype = c_void_p
        tonlib_json_client_create.argtypes = []
        try:
            self._client = tonlib_json_client_create()
        except Exception:
            asyncio.ensure_future(self.restart_hook(), loop=loop)

        tonlib_json_client_receive = tonlib.tonlib_client_json_receive
        tonlib_json_client_receive.restype = c_char_p
        tonlib_json_client_receive.argtypes = [c_void_p, c_double]
        self._tonlib_json_client_receive = tonlib_json_client_receive

        tonlib_json_client_send = tonlib.tonlib_client_json_send
        tonlib_json_client_send.restype = None
        tonlib_json_client_send.argtypes = [c_void_p, c_char_p]
        self._tonlib_json_client_send = tonlib_json_client_send

        tonlib_json_client_execute = tonlib.tonlib_client_json_execute
        tonlib_json_client_execute.restype = c_char_p
        tonlib_json_client_execute.argtypes = [c_void_p, c_char_p]
        self._tonlib_json_client_execute = tonlib_json_client_execute

        tonlib_json_client_destroy = tonlib.tonlib_client_json_destroy
        tonlib_json_client_destroy.restype = None
        tonlib_json_client_destroy.argtypes = [c_void_p]
        self._tonlib_json_client_destroy = tonlib_json_client_destroy

        self.futures = {}
        self.loop = loop
        self.ls_index = ls_index
        self.read_results_task = asyncio.ensure_future(self.read_results(), loop=self.loop)
        self.del_expired_futures_task = asyncio.ensure_future(self.del_expired_futures(), loop=self.loop)
        self.shutdown_state = False  # False, "started", "finished"
        self.request_num = 0
        self.max_requests = None

    def __del__(self):
        try:
            self._tonlib_json_client_destroy(self._client)
        except Exception:
            asyncio.ensure_future(self.restart_hook(), loop=self.loop)

    def send(self, query):
        query = json.dumps(query).encode('utf-8')
        try:
            self._tonlib_json_client_send(self._client, query)
        except Exception:
            asyncio.ensure_future(self.restart_hook(), loop=self.loop)

    def receive(self, timeout=10):
        result = None
        try:
            result = self._tonlib_json_client_receive(self._client, timeout)
        except Exception:
            asyncio.ensure_future(self.restart_hook(), loop=self.loop)
        if result:
            result = json.loads(result.decode('utf-8'))
        return result

    def set_restart_hook(self, hook, max_requests):
        self.max_requests = max_requests
        self.restart_hook = hook

    def execute(self, query, timeout=settings.pyton.request_timeout):
        extra_id = "%s:%s:%s" % (time.time()+timeout, self.ls_index, random.random())
        query["@extra"] = extra_id
        self.loop.run_in_executor(None, lambda: self.send(query))
        future_result = self.loop.create_future()
        self.futures[extra_id] = future_result
        self.request_num += 1
        if self.max_requests and self.max_requests < self.request_num:
            asyncio.ensure_future(self.restart_hook(), loop=self.loop)
        return future_result

    async def read_results(self):
        while True:
            result = None
            try:
                timeout = 3
                delta = 0.5
                f = functools.partial(self.receive, timeout)
                result = await asyncio.wait_for(self.loop.run_in_executor(None, f), timeout=timeout + delta)
            except asyncio.TimeoutError:
                logger.warning("Tonlib Stuck!")
                asyncio.ensure_future(self.restart_hook(), loop=self.loop)
            except Exception as e:
                logger.warning("Tonlib crashed!")
                asyncio.ensure_future(self.restart_hook(), loop=self.loop)
            if result and isinstance(result, dict) and ("@extra" in result) and (result["@extra"] in self.futures):
                try:
                    if not self.futures[result["@extra"]].done():
                        self.futures[result["@extra"]].set_result(result)
                        self.futures.pop(result["@extra"])
                except Exception as e:
                    logger.error(f'Tonlib receiving result exception: {e}')

            if (not len(self.futures)) and (self.shutdown_state in ["started", "finished"]):
                break
        self.shutdown_state = "finished"

    async def del_expired_futures(self):
        while True:
            now = time.time()
            to_del = []
            for i in self.futures:
                if float(i.split(":")[0]) > now:
                    break
                if self.futures[i].done():
                    to_del.append(i)
                    continue
                to_del.append(i)
                self.futures[i].cancel()
            for i in to_del:
                self.futures.pop(i)

            if (not len(self.futures)) and (self.shutdown_state in ["started", "finished"]):
                break

            await asyncio.sleep(1)
