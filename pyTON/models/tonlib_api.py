from pydantic import BaseModel, Field

from pyTON.models.fields import Int64, Bytes, Int32, Int53

"""
List of models, which represent objects described in TL specification:
https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl
"""


class TLObject(BaseModel):
    type: str = Field(alias="@type", title="TypeLanguage constructor type name.")


class TonLibExecutionResult(BaseModel):
    extra: str = Field(alias="@extra")


# TL Spec:
# https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl#L50
class TonBlockIdExt(TLObject):
    workchain: int = Int32()
    shard: str = Int64()
    seqno: int = Int32()
    root_hash: str = Bytes()
    file_hash: str = Bytes()


# TL Spec:
# https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl#L47
class InternalTransactionId(TLObject):
    lt: str = Int64()
    hash: str = Bytes()


# TL Spec:
# https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl#L52
class RawFullAccountState(TLObject):
    balance: str = Int64()
    code: str = Bytes()
    data: str = Bytes()
    last_transaction_id: InternalTransactionId
    block_id: TonBlockIdExt
    frozen_hash: str = Bytes()
    sync_utime: int = Int53()
