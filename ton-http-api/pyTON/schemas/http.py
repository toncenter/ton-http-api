from typing import Optional, TypeVar, Union, List, Literal, Tuple
from pydantic.generics import GenericModel, Generic
from pydantic import BaseModel, Field

from .ton import (
    ConfigInfo,
    TVMStackEntryType,
    TvmTuple,
    BlockIdExt,
    TransactionId,
    BlockId,
    AccountState,
    AddressShort,
    JettonContent,
    Transaction,
    RawTransaction,
)

ResultT = TypeVar("ResultT")


class TonResponseGeneric(GenericModel, Generic[ResultT]):
    ok: bool
    result: Optional[ResultT]
    error: Optional[str] = None
    code: Optional[int] = None


class TonResponse200Generic(GenericModel, Generic[ResultT]):
    ok: bool = Field(True)
    result: Optional[ResultT]


ResultTypeT = TypeVar("ResultTypeT")


class TonResponseResultGeneric(GenericModel, Generic[ResultTypeT]):
    type: ResultTypeT = Field(alias="@type")
    extra: str = Field(alias="@extra")


class TonResponse(TonResponseGeneric[Union[str, list, dict, None]]):
    pass


class ErrorGetAddressInformationResponses422(BaseModel):
    ok: bool = Field(False)
    error: str
    code: int = Field(422)

    @staticmethod
    def get_response():
        return {
            422: {
                "model": ErrorGetAddressInformationResponses422,
                "description": "Validation Error",
            }
        }


class ErrorGetAddressInformationResponses504(BaseModel):
    ok: bool = Field(False)
    error: str
    code: int = Field(504)

    @staticmethod
    def get_response():
        return {
            504: {
                "model": ErrorGetAddressInformationResponses504,
                "description": "Lite Server Timeout",
            }
        }


def get_get_address_information_error_responses():
    response = ErrorGetAddressInformationResponses422.get_response()
    response.update(ErrorGetAddressInformationResponses504.get_response())
    return response


class GetAddressInformationResponse(BaseModel):
    type: str = Field(alias="@type")
    balance: str
    code: str
    data: str
    last_transaction_id: TransactionId
    block_id: BlockId
    frozen_hash: str
    sync_utime: int
    extra: str = Field(alias="@extra")
    state: str


class GetExtendedAddressInformationResponse(BaseModel):
    type: str = Field(alias="@type")
    address: AddressShort
    balance: str
    last_transaction_id: TransactionId
    block_id: BlockId
    sync_utime: int
    account_state: AccountState
    revision: int
    extra: str = Field(alias="@extra")


class GetWalletInformationResponse(BaseModel):
    wallet: bool
    balance: str
    account_state: str
    wallet_type: str
    seqno: int
    last_transaction_id: TransactionId
    wallet_id: int


class GetAddressBalanceResponse(BaseModel):
    ok: bool = Field(example=True)
    result: str = Field(
        example="1234",
        description="str representation of number, balance of the contract",
    )


class GetAddressStateResponse(BaseModel):
    ok: bool = Field(True)
    result: Literal["nonexist", "uninit", "active", "frozen"] = Field(
        description="State of the address, visit https://docs.ton.org/learn/overviews/addresses#addresses-state for more"
    )


class PackAddressResponse(BaseModel):
    ok: bool = Field(True)
    result: str = Field(
        example="EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N",
        description="Packed address",
    )


class UnpackAddressResponse(BaseModel):
    ok: bool = Field(True)
    result: str = Field(
        example="0:83dfd552e63729b472fcbcc8c45ebcc6691702558b68ec7527e1ba403a0f31a8",
        description="Unpacked address",
    )


class GetTokenDataResponse(BaseModel):
    total_supply: int
    mintable: bool
    admin_address: str
    jetton_content: JettonContent
    jetton_wallet_code: str
    contract_type: str


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
    jsonrpc: Literal["2.0"] = "2.0"


class TonRequestJsonRPC(BaseModel):
    method: str = Field(example="runGetMethod")
    params: dict = Field(
        {},
        example={
            "address": "kQAl8r8c6Pg-0MD9c-onqsdwk83PkAx1Cwcd9_sCiOAZsoUE",
            "method": "get_jetton_data",
            "stack": [],
        },
    )
    id: Optional[str] = None
    jsonrpc: Optional[str] = None


class GetConfigParamResponse(TonResponseGeneric[ConfigInfo]):
    pass


class RunGetMethodResult(BaseModel):
    type: Literal["smc.runResult"] = Field(alias="@type")
    gas_used: int
    stack: List[List[Union[TVMStackEntryType, Union[str, TvmTuple]]]] = Field(
        example=[["num", "0x1"]]
    )
    exit_code: int
    extra: str = Field(alias="@extra")
    block_id: BlockIdExt
    last_transaction_id: TransactionId


class RunGetMethodResponse(TonResponseGeneric[RunGetMethodResult]):
    pass


class OkResponse(TonResponseGeneric[TonResponseResultGeneric[Literal["ok"]]]):
    pass


class SendBocReturnHashResult(TonResponseResultGeneric[Literal["raw.extMessageInfo"]]):
    hash: str = Field(example="65+BlkfroywqXyM+POVpMpFiC6XYMQyBvHXw12XiFzc=")


class SendBocReturnHashResponse(TonResponseGeneric[SendBocReturnHashResult]):
    pass


class Fees(BaseModel):
    type: Literal["fees"] = Field(alias="@type")
    in_fwd_fee: int
    storage_fee: int
    gas_fee: int
    fwd_fee: int


class EstimateFeeResponseResult(BaseModel):
    type: Literal["query.fees"] = Field(alias="@type")
    source_fees: Fees
    destination_fees: List[Fees]
    extra: str = Field(alias="@extra")


class EstimateFeeResponse(TonResponseGeneric[EstimateFeeResponseResult]):
    pass
