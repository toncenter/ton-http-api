from typing import Optional, TypeVar, Union, Literal
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
    jsonrpc: Literal['2.0'] = "2.0"


class TonRequestJsonRPC(BaseModel):
    method: str = Field(example='runGetMethod')
    params: dict = Field({}, example={"address": "kQAl8r8c6Pg-0MD9c-onqsdwk83PkAx1Cwcd9_sCiOAZsoUE", "method": "get_jetton_data", "stack": [] } )
    id: Optional[str] = None
    jsonrpc: Optional[str] = None
