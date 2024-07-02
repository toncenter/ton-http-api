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
    type: Literal['string'] = Field(alias="@extra")

class TonResponseGetBlockTransactions(BaseModel):
    ok: bool
    result: Optional[ResponseShortTransaction]
    error: Optional[str] = None
    code: Optional[int] = None

class Address(BaseModel):
    type: Literal['accountAddress'] = Field(alias="@type")
    account_address: str

class TransactionId(BaseModel):
    type: Literal['internal.transactionId'] = Field(alias="@type")
    account_address: str
    lt: str
    hash: str

class MsgData(BaseModel):
    type: Literal['msg.dataRaw'] = Field(alias="@type")
    body: str
    init_state: str

class Msg(BaseModel):
    type: Literal['raw.message'] = Field(alias="@type")
    source: str
    destination: str
    value: str
    fwd_fee: str
    ihr_fee: str
    created_lt: str
    body_hash: str
    msg_data: MsgData
    message: str


class ResponseAddressTransaction(BaseModel):
    type: Literal['raw.transaction'] = Field(alias="@type")
    address: Address
    utime: int
    data: str
    transaction_id: TransactionId
    fee: str
    storage_fee: str
    other_fee: str
    in_msg: Msg
    out_msgs: List[Msg]


class TonResponseGetTransactions(BaseModel):
    ok: bool
    result: Optional[List[ResponseAddressTransaction]]
    error: Optional[str] = None
    code: Optional[int] = None

class TonTryLocateTx(BaseModel):
    ok: bool
    result: Optional[List[ResponseAddressTransaction]]
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
