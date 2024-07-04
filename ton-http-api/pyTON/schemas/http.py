from typing import Optional, TypeVar, Union, Literal, List, Tuple
from pydantic.generics import GenericModel, Generic
from pydantic import BaseModel, Field

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


class DeprecatedTonResponseJsonRPC(BaseModel):
    ok: bool
    result: Optional[ResultT]
    error: Optional[str] = None
    code: Optional[int] = None
    id: str
    jsonrpc: str = "2.0"


class TonRequestJsonRPC(BaseModel):
    method: str
    params: dict = {}
    id: Optional[str] = None
    jsonrpc: Optional[str] = None


class TvmStackEntry(BaseModel):
    type: str = Field(alias='@type')


class TvmTuple(BaseModel):
    type: Literal['tvm.tuple'] = Field(alias='@type')
    elements: List[TvmStackEntry]


class BlockIdExt(BaseModel):
    type: Literal['smc.blockIdExt'] = Field(alias='@type')
    workchain: int
    shard: str
    seqno: int
    root_hash: str
    file_hash: str


class TransactionId(BaseModel):
    type: Literal['internal.transactionId'] = Field(alias='@type')
    lt: str
    hash: str


TVMStackEntryType = Literal['cell', 'slice', 'num', 'tuple', 'list']

class RunGetMethodResult(BaseModel):
    type: Literal['smc.runResult'] = Field(alias='@type')
    gas_used: int
    stack: List[List[Union[TVMStackEntryType, Union[str, TvmTuple]]]] = Field(example=[['num', '0x1']])
    exit_code: int
    extra: str = Field(alias='@extra')
    block_id: BlockIdExt
    last_transaction_id: TransactionId


class RunGetMethodResponse(TonResponseGeneric[RunGetMethodResult]):
    pass
