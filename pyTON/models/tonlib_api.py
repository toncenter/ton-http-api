from pydantic import BaseModel, Field
from pyTON.models.fields import Int64, Bytes, Int32, Int53

"""
List of models, which represent objects described in TL specification:
https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl
"""


class TLObject(BaseModel):
    type: str = Field(alias="@type", title="TL Object type name.")


class TonLibExecutionResult(BaseModel):
    extra: str = Field(alias="@extra")


class TonBlockIdExt(TLObject):
    """
    TL Specification: https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl#L50
    """
    workchain: int = Int32()
    shard: str = Int64()
    seqno: int = Int32()
    root_hash: str = Bytes()
    file_hash: str = Bytes()


class InternalTransactionId(TLObject):
    """
    TL Specification: https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl#L47
    """
    lt: str = Int64()
    hash: str = Bytes()


class RawFullAccountState(TLObject):
    """
    TL Specification: https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/tl/generate/scheme/tonlib_api.tl#L52
    """
    balance: str = Int64()
    code: str = Bytes()
    data: str = Bytes()
    last_transaction_id: InternalTransactionId
    block_id: TonBlockIdExt
    frozen_hash: str = Bytes()
    sync_utime: int = Int53()
