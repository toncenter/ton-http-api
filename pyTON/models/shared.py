from typing import Optional, Union, TypeVar, Literal
from pyTON.models.tonlib_api import RawFullAccountState, TonLibExecutionResult

from pydantic import BaseModel
from pydantic.generics import GenericModel, Generic

"""
Util classes used to generate new response models.
"""

ResultT = TypeVar('ResultT')


class TonResponseGeneric(GenericModel, Generic[ResultT]):
    ok: bool
    result: ResultT
    error: Optional[str] = None
    code: Optional[int] = None


"""
Responses specific to some API methods.
"""


class TonResponseDefault(TonResponseGeneric[Union[str, list, dict, None]]):
    pass


"""
GET /getAddressInformation.
"""


class GetAddressInformationResult(RawFullAccountState, TonLibExecutionResult):
    state: Literal["uninitialized", "frozen", "active"]


class TonResponseGetAddressInformation(TonResponseGeneric[GetAddressInformationResult]):
    pass


"""
JSON RPC models.
"""


class TonResponseJsonRPC(TonResponseDefault):
    jsonrpc: str = "2.0"
    id: Optional[str] = None


class TonRequestJsonRPC(BaseModel):
    method: str
    params: dict = {}
    id: Optional[str] = None
    jsonrpc: Optional[str] = None
