from typing import Optional, TypeVar, Union, List, Literal
from pydantic.generics import GenericModel, Generic
from pydantic import BaseModel, Field

from .ton import ConfigInfo

ResultT = TypeVar('ResultT')


class TonResponseGeneric(GenericModel, Generic[ResultT]):
    ok: bool
    result: Optional[ResultT]
    error: Optional[str] = None
    code: Optional[int] = None


class TonResponse200Generic(GenericModel, Generic[ResultT]):
    ok: bool = Field(True)
    result: Optional[ResultT]


class TonResponse(TonResponseGeneric[Union[str, list, dict, None]]):
    pass


class ErrorGetAddressInformationResponses422(BaseModel):
    ok: bool = Field(False)
    error: str
    code: int = Field(422)

    @staticmethod
    def get_response():
        return {422: {"model": ErrorGetAddressInformationResponses422, 'description': 'Validation Error'}}


class ErrorGetAddressInformationResponses504(BaseModel):
    ok: bool = Field(False)
    error: str
    code: int = Field(504)

    @staticmethod
    def get_response():
        return {504: {"model": ErrorGetAddressInformationResponses504, 'description': 'Lite Server Timeout'}}


def get_get_address_information_error_responses():
    response = ErrorGetAddressInformationResponses422.get_response()
    response.update(ErrorGetAddressInformationResponses504.get_response())
    return response


class GetAddressInformationResponse(BaseModel):
    type: str = Field(alias="@type")
    balance: str
    code: str
    data: str

    class LastTransactionId(BaseModel):
        type: str = Field(alias="@type")
        lt: str
        hash: str

    last_transaction_id: LastTransactionId

    class BlockId(BaseModel):
        type: str = Field(alias="@type")
        workchain: int
        shard: str
        seqno: int
        root_hash: str
        file_hash: str

    block_id: BlockId
    frozen_hash: str
    sync_utime: int
    extra: str = Field(alias="@extra")
    state: str


class GetExtendedAddressInformationResponse(BaseModel):
    type: str = Field(alias="@type")

    class Address(BaseModel):
        type: str = Field(alias="@type")
        account_address: str

    address: Address
    balance: str

    class LastTransactionId(BaseModel):
        type: str = Field(alias="@type")
        lt: str
        hash: str

    last_transaction_id: LastTransactionId

    class BlockId(BaseModel):
        type: str = Field(alias="@type")
        workchain: int
        shard: str
        seqno: int
        root_hash: str
        file_hash: str

    block_id: BlockId

    sync_utime: int

    class AccountState(BaseModel):
        type: str = Field(alias="@type")
        wallet_id: str
        seqno: int

    account_state: AccountState

    revision: int
    extra: str = Field(alias="@extra")


class GetWalletInformationResponse(BaseModel):
    wallet: bool
    balance: str
    account_state: str
    wallet_type: str
    seqno: int

    class LastTransactionId(BaseModel):
        type: str = Field(alias="@type")
        lt: str
        hash: str

    last_transaction_id: LastTransactionId
    wallet_id: int


# should be list
class GetTransactionsResponse(BaseModel):
    type: str = Field(alias="@type")
    address: dict
    utime: int
    data: str

    class TransactionId(BaseModel):
        type: str = Field(alias="@type")
        lt: str
        hash: str

    transaction_id: TransactionId
    fee: str
    storage_fee: str
    other_fee: str

    class Message(BaseModel):
        type: str = Field(alias="@type")
        source: str
        destination: str
        value: str
        fwd_fee: str
        ihr_fee: str
        created_lt: str
        body_hash: str

        class MessageData(BaseModel):
            type: str = Field(alias="@type")
            body: str
            init_state: Optional[str] = None

        msg_data: MessageData
        message: Optional[str] = None

    in_msg: Message
    out_msgs: List[Message]


class GetAddressBalanceResponse(BaseModel):
    ok: bool = Field(True)
    result: str = Field('1234', description='str representation of number, balance of the contract')


class GetAddressStateResponse(BaseModel):
    ok: bool = Field(True)
    result: str = Field('nonexist/uninit/active/frozen',
                        description='State of the address, visit https://docs.ton.org/learn/overviews/addresses#addresses-state for more')


class PackAddressResponse(BaseModel):
    ok: bool = Field(True)
    result: str = Field('EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N', description='Packed address')


class UnpackAddressResponse(BaseModel):
    ok: bool = Field(True)
    result: str = Field('0:83dfd552e63729b472fcbcc8c45ebcc6691702558b68ec7527e1ba403a0f31a8',
                        description='Unpacked address')


class GetTokenDataResponse(BaseModel):
    total_supply: int
    mintable: bool
    admin_address: str

    class JettonContent(BaseModel):
        type: str = Field(alias="@type")

        class Data(BaseModel):
            image: str
            name: str
            symbol: str
            description: str
            decimals: str

        data: Data

    jetton_content: JettonContent

    jetton_wallet_code: str
    contract_type: str


class DetectAddressResponse(BaseModel):
    raw_form: str

    class Bouncable(BaseModel):
        b64: str
        b64url: str

    bounceable: Bouncable
    non_bounceable: Bouncable
    given_type: str
    test_only: bool


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


class GetConfigParamResponse(TonResponseGeneric[ConfigInfo]):
    pass
