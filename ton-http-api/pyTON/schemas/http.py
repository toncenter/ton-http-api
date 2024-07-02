from typing import Optional, TypeVar, Union, Literal, List
from pydantic.generics import GenericModel, Generic
from pydantic import BaseModel, Field

ResultT = TypeVar('ResultT')


class TonResponseGeneric(GenericModel, Generic[ResultT]):
    ok: bool
    result: Optional[ResultT]
    error: Optional[str] = None
    code: Optional[int] = None


ResultTypeT = TypeVar('ResultTypeT')


class TonResponseResultGeneric(GenericModel, Generic[ResultTypeT]):
    type: ResultTypeT = Field(alias="@type")
    extra: str = Field(alias="@extra")


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


class OkResponse(TonResponseGeneric[TonResponseResultGeneric[Literal['ok']]]):
    pass


class SendBocReturnHashResult(TonResponseResultGeneric[Literal['raw.extMessageInfo']]):
    hash: str = Field(example="65+BlkfroywqXyM+POVpMpFiC6XYMQyBvHXw12XiFzc=")


class SendBocReturnHashResponse(TonResponseGeneric[SendBocReturnHashResult]):
    pass


class Fees(BaseModel):
    type: Literal['fees'] = Field(alias="@type")
    in_fwd_fee: int
    storage_fee: int
    gas_fee: int
    fwd_fee: int


class EstimateFeeResponseResult(BaseModel):
    type: Literal['query.fees'] = Field(alias="@type")
    source_fees: Fees
    destination_fees: List[Fees]
    extra: str = Field(alias="@extra")


class EstimateFeeResponse(TonResponseGeneric[EstimateFeeResponseResult]):
    pass
