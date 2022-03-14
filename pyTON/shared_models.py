from pydantic import BaseModel, Field


class TonResponseLastTransactionId(BaseModel):
    type: str = Field(alias="@type")
    lt: str
    hash: str


class TonResponseBlockId(BaseModel):
    type: str = Field(alias="@type")
    workchain: int
    shard: str
    seqno: int
    root_hash: str
    file_hash: str


class TonResponseAddress(BaseModel):
    type: str = Field(alias="@type")
    account_address: str


class TonResponseAccountState(BaseModel):
    type: str = Field(alias="@type")
    wallet_id: str
    seqno: int
