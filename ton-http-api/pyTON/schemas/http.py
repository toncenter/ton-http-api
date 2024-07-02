from typing import Optional, TypeVar, Union, Literal, List
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

class ShortTransaction(BaseModel):
    type: Literal['blocks.shortTxId'] = Field(alias="@type")
    mode: int
    account: str
    lt: str
    hash: str

class Id(BaseModel):
    type: Literal['ton.blockIdExt'] = Field(alias="@type")
    workchain: int
    shard: str
    seqno: int
    root_hash: str
    file_hash: str

class ResponseShortTransaction(BaseModel):
    type: Literal['blocks.transactions'] = Field(alias="@type")
    id: Id
    req_count: int
    incomplete: bool
    transactions: List[ShortTransaction]
    type: Literal['string'] = Field(alias="@@xtra")

class TonResponseGetBlockTransactions(BaseModel):
    ok: bool
    result: Optional[ResponseShortTransaction]
    error: Optional[str] = None
    code: Optional[int] = None

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
