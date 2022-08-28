from typing import Optional, TypeVar, Union, Dict, Any, List, Literal
from pydantic import BaseModel
from pydantic.generics import GenericModel, Generic

from pytonlib.utils.wallet import wallets as known_wallets, sha256

from enum import Enum
from dataclasses import dataclass


@dataclass
class TonlibClientResult:
    task_id: str
    method: str
    elapsed_time: float
    params: Optional[Any] = None
    result: Optional[Any] = None
    exception: Optional[Exception] = None
    liteserver_info: Optional[Any] = None


class TonlibWorkerMsgType(Enum):
    TASK_RESULT = 0
    LAST_BLOCK_UPDATE = 1
    ARCHIVAL_UPDATE = 2


@dataclass
class ConsensusBlock:
    seqno: int = 0
    timestamp: int = 0

"""
Util classes used to generate new response models.
"""

ResultT = TypeVar('ResultT')


class TonResponseGeneric(GenericModel, Generic[ResultT]):
    ok: bool
    result: Optional[ResultT]
    error: Optional[str] = None
    code: Optional[int] = None

class TonResponse(TonResponseGeneric[Union[str, list, dict, None]]):
    pass



class TonResponseJsonRPC(BaseModel):
    id: str
    jsonrpc: str = "2.0"
    result: Optional[ResultT]
    error: Optional[str] = None
    code: Optional[int] = None


class TonRequestJsonRPC(BaseModel):
    method: str
    params: dict = {}
    id: Optional[str] = None
    jsonrpc: Optional[str] = None

def check_tonlib_type(tl_obj: dict, expected_type: str):
    tl_type = tl_obj.get('@type', '')
    if tl_type != expected_type:
        raise Exception(f"Unexpected TL object type {tl_type}")

def address_state(account_info):
    if len(account_info.get("code", "")) == 0:
        if len(account_info.get("frozen_hash", "")) == 0:
            return "uninitialized"
        else:
            return "frozen"
    return "active"

class BlockId(BaseModel):
    workchain: int
    shard: int
    seqno: int
    root_hash: str
    file_hash: str

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, 'ton.blockIdExt')

        workchain = int(tl_obj['workchain'])
        shard = int(tl_obj['shard'])
        seqno = int(tl_obj['seqno'])
        root_hash = tl_obj['root_hash']
        file_hash = tl_obj['file_hash']

        return BlockId(workchain=workchain, shard=shard, seqno=seqno, root_hash=root_hash, file_hash=file_hash)

class SmartContract(BaseModel):
    balance: int
    code: Optional[str]
    data: Optional[str]
    last_transaction_lt: Optional[int]
    last_transaction_hash: Optional[str]
    frozen_hash: Optional[str]
    state: Literal['active', 'frozen', 'uninitialized']
    contract_type: Optional[str]
    contract_extracted_data: Optional[dict]
    block_id: BlockId

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, 'raw.fullAccountState')

        balance = int(tl_obj['balance']) if int(tl_obj['balance']) > 0 else 0
        state = address_state(tl_obj)
        block_id = BlockId.build(tl_obj['block_id'])

        obj = SmartContract(balance=balance, state=state, block_id=block_id)

        if len(tl_obj['code']):
            obj.code = tl_obj['code']
        if len(tl_obj['data']):
            obj.data = tl_obj['data']
        if int(tl_obj['last_transaction_id']['lt']):
            obj.last_transaction_lt = int(tl_obj['last_transaction_id']['lt'])
            obj.last_transaction_hash = tl_obj['last_transaction_id']['hash']
        if len(tl_obj['frozen_hash']):
            obj.frozen_hash = tl_obj['frozen_hash']

        ci = sha256(tl_obj['code'])
        if ci in known_wallets:
            wallet_handler = known_wallets[ci]
            obj.contract_type = wallet_handler['type']
            obj.contract_extracted_data = {}
            wallet_handler["data_extractor"](obj.contract_extracted_data, tl_obj)

        return obj


