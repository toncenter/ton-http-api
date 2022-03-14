from typing import Optional, Union
from pydantic import BaseModel, Field
from pyTON.shared_models import TonResponseLastTransactionId, TonResponseBlockId, TonResponseAddress, \
    TonResponseAccountState

"""
Base TON responses.
"""


class TonResponse(BaseModel):
    ok: bool
    result: Union[str, list, dict, None] = None
    error: Optional[str] = None
    code: Optional[int] = None


class TonResponseJsonRPC(TonResponse):
    jsonrpc: str = "2.0"
    id: Optional[str] = None


class TonRequestJsonRPC(BaseModel):
    method: str
    params: dict = {}
    id: Optional[str] = None
    jsonrpc: Optional[str] = None


"""
Responses specific to some API methods.
"""

"""
GET /getAddressInformation.
"""


class TonResponseGetAddressInformationResult(BaseModel):
    type: str = Field(alias="@type")
    balance: str
    code: str
    data: str
    last_transaction_id: TonResponseLastTransactionId
    block_id: TonResponseBlockId
    frozen_hash: str
    sync_utime: int
    extra: str = Field(alias="@extra")
    state: str


class TonResponseGetAddressInformation(TonResponse):
    result: TonResponseGetAddressInformationResult


"""
GET /getExtendedAddressInformation.
"""


class TonResponseGetExtendedAddressInformationResult(BaseModel):
    type: str = Field(alias="@type")
    address: TonResponseAddress
    balance: str
    last_transaction_id: TonResponseLastTransactionId
    block_id: TonResponseBlockId
    sync_utime: int
    account_state: TonResponseAccountState
    revision: int
    extra: str = Field(alias="@extra")


class TonResponseGetExtendedAddressInformation(TonResponse):
    result: TonResponseGetExtendedAddressInformationResult
