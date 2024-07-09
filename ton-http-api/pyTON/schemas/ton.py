from typing import List, Optional, Literal, TypeVar
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel, Generic

from pytonlib.utils.wallet import wallets as known_wallets, sha256

ResultT = TypeVar("ResultT")


def check_tonlib_type(tl_obj: dict, expected_type: str):
    tl_type = tl_obj.get("@type", "")
    if tl_type != expected_type:
        raise Exception(f"Unexpected TL object type {tl_type}")


def address_state(account_info):
    if len(account_info.get("code", "")) == 0:
        if len(account_info.get("frozen_hash", "")) == 0:
            return "uninitialized"
        else:
            return "frozen"
    return "active"


class BlockId(BaseModel):
    workchain: int
    shard: str
    seqno: int
    root_hash: str
    file_hash: str

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "ton.blockIdExt")

        workchain = int(tl_obj["workchain"])
        shard = tl_obj["shard"]
        seqno = int(tl_obj["seqno"])
        root_hash = tl_obj["root_hash"]
        file_hash = tl_obj["file_hash"]

        return BlockId(
            workchain=workchain,
            shard=shard,
            seqno=seqno,
            root_hash=root_hash,
            file_hash=file_hash,
        )


class BlockHeader(BaseModel):
    type: Literal["blocks.header"] = Field(alias="@type")
    id: BlockId
    global_id: int
    version: int
    flags: int
    after_merge: bool
    after_split: bool
    before_split: bool
    want_merge: bool
    want_split: bool
    validator_list_hash_short: int
    catchain_seqno: int
    min_ref_mc_seqno: int
    is_key_block: bool
    prev_key_block_seqno: int
    start_lt: int
    end_lt: int
    gen_utime: int
    vert_seqno: int
    prev_blocks: List[BlockId]

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "blocks.header")
        print(tl_obj)
        return BlockHeader(
            id=BlockId.build(tl_obj["id"]),
            global_id=tl_obj["global_id"],
            version=tl_obj["version"],
            flags=tl_obj.get("flags", 0),
            after_merge=tl_obj["after_merge"],
            after_split=tl_obj["after_split"],
            before_split=tl_obj["before_split"],
            want_merge=tl_obj["want_merge"],
            want_split=tl_obj["want_split"],
            validator_list_hash_short=tl_obj["validator_list_hash_short"],
            catchain_seqno=tl_obj["catchain_seqno"],
            min_ref_mc_seqno=tl_obj["min_ref_mc_seqno"],
            is_key_block=tl_obj["is_key_block"],
            prev_key_block_seqno=tl_obj["prev_key_block_seqno"],
            start_lt=tl_obj["start_lt"],
            end_lt=tl_obj["end_lt"],
            gen_utime=tl_obj["gen_utime"],
            vert_seqno=tl_obj.get("vert_seqno", 0),
            prev_blocks=(BlockId.build(p) for p in tl_obj["prev_blocks"]),
        )


class SmartContract(BaseModel):
    balance: int
    code: Optional[str]
    data: Optional[str]
    last_transaction_lt: Optional[int]
    last_transaction_hash: Optional[str]
    frozen_hash: Optional[str]
    state: Literal["active", "frozen", "uninitialized"]
    contract_type: Optional[str]
    contract_extracted_data: Optional[dict]
    block_id: BlockId

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "raw.fullAccountState")

        balance = int(tl_obj["balance"]) if int(tl_obj["balance"]) > 0 else 0
        state = address_state(tl_obj)
        block_id = BlockId.build(tl_obj["block_id"])

        obj = SmartContract(balance=balance, state=state, block_id=block_id)

        if len(tl_obj["code"]):
            obj.code = tl_obj["code"]
        if len(tl_obj["data"]):
            obj.data = tl_obj["data"]
        if int(tl_obj["last_transaction_id"]["lt"]):
            obj.last_transaction_lt = int(tl_obj["last_transaction_id"]["lt"])
            obj.last_transaction_hash = tl_obj["last_transaction_id"]["hash"]
        if len(tl_obj["frozen_hash"]):
            obj.frozen_hash = tl_obj["frozen_hash"]

        ci = sha256(tl_obj["code"])
        if ci in known_wallets:
            wallet_handler = known_wallets[ci]
            obj.contract_type = wallet_handler["type"]
            obj.contract_extracted_data = {}
            wallet_handler["data_extractor"](obj.contract_extracted_data, tl_obj)

        return obj


class AdressUserFriendly(BaseModel):
    b64: str
    b64url: str

    def build(raw: dict):
        return AdressUserFriendly(b64=raw["b64"], b64url=raw["b64url"])


class AddressForms(BaseModel):
    raw_form: str
    bounceable: AdressUserFriendly
    non_bounceable: AdressUserFriendly
    given_type: Literal["friendly_bounceable", "friendly_non_bounceable", "raw_form"]
    test_only: bool

    def build(raw: dict):
        return AddressForms(
            raw_form=raw["raw_form"],
            bounceable=AdressUserFriendly.build(raw["bounceable"]),
            non_bounceable=AdressUserFriendly.build(raw["non_bounceable"]),
            given_type=raw["given_type"],
            test_only=raw["test_only"],
        )


class MasterchainInfo(BaseModel):
    type: Literal["blocks.masterchainInfo"] = Field(alias="@type")
    last: BlockId
    state_root_hash: str
    init: BlockId

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "blocks.masterchainInfo")

        return MasterchainInfo(
            last=BlockId.build(tl_obj["last"]),
            init=BlockId.build(tl_obj["init"]),
            state_root_hash=tl_obj["state_root_hash"],
        )


class BlockSignature(BaseModel):
    type: Literal["blocks.signature"] = Field(alias="@type")
    node_id_short: str
    signature: str


class MasterchainSignatures(BaseModel):
    type: Literal["blocks.blockSignatures"] = Field(alias="@type")
    id: BlockId
    signatures: List[BlockSignature]


class Proof(BaseModel):
    type: Literal["blocks.blockLinkBack"] = Field(alias="@type")
    to_key_block: bool
    from_id: BlockId = Field(alias="from")
    to: BlockId
    dest_proof: str
    proof: str
    state_proof: str


class ShardBlockProof(BaseModel):
    type: Literal["blocks.blockSignatures"] = Field(alias="@type")
    from_id: BlockId = Field(alias="from")
    mc_id: BlockId
    links: List[str]
    mc_proof: List[Proof]


class Shards(BaseModel):
    type: Literal["blocks.shards"] = Field(alias="@type")
    shards: List[BlockId]


class ConsensusBlock(BaseModel):
    consensus_block: int
    timestamp: int


class ShortTransaction(BaseModel):
    type: Literal["blocks.shortTxId"] = Field(alias="@type")
    mode: int
    account: str
    lt: str
    hash: str


class ShortTransactions(BaseModel):
    type: Literal["blocks.transactions"] = Field(alias="@type")
    id: BlockId
    req_count: int
    incomplete: bool
    transactions: List[ShortTransaction]


class ExternalMessage(BaseModel):
    msg_hash: str

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "raw.extMessageInfo")

        return ExternalMessage(msg_hash=tl_obj["hash"])


class SerializedBoc(BaseModel):
    boc: str

    def build_from_config(tl_obj: dict):
        check_tonlib_type(tl_obj, "configInfo")

        return SerializedBoc(boc=tl_obj["config"]["bytes"])


class MsgDataRaw(BaseModel):
    body: str
    init_state: str

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "msg.dataRaw")

        return MsgDataRaw(body=tl_obj["body"], init_state=tl_obj["init_state"])


class Message(BaseModel):
    source: str
    destination: str
    value: int
    fwd_fee: int
    ihr_fee: int
    created_lt: int
    body_hash: str
    msg_data: MsgDataRaw
    comment: Optional[str]
    op: Optional[int]

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "raw.message")

        return Message(
            source=tl_obj["source"],
            destination=tl_obj["destination"],
            value=int(tl_obj["value"]),
            fwd_fee=int(tl_obj["fwd_fee"]),
            ihr_fee=int(tl_obj["ihr_fee"]),
            created_lt=int(tl_obj["created_lt"]),
            body_hash=tl_obj["body_hash"],
            msg_data=MsgDataRaw.build(tl_obj["msg_data"]),
            comment=tl_obj.get("comment"),
            op=tl_obj.get("op"),
        )


class TransactionId(BaseModel):
    lt: int
    hash: str

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "internal.transactionId")

        return TransactionId(lt=int(tl_obj["lt"]), hash=tl_obj["hash"])


class TransactionWAddressId(TransactionId):
    account_address: str


class Address(BaseModel):
    type: Literal["accountAddress"] = Field(alias="@type")
    account_address: str


class Transaction(BaseModel):
    utime: int
    data: str
    hash: str
    lt: str
    fee: int
    storage_fee: int
    other_fee: int
    in_msg: Optional[Message]
    out_msgs: List[Message]

    def build(tl_obj: dict):
        check_tonlib_type(tl_obj, "raw.transaction")

        return Transaction(
            utime=int(tl_obj["utime"]),
            data=tl_obj["data"],
            hash=tl_obj["transaction_id"]["hash"],
            lt=tl_obj["transaction_id"]["lt"],
            fee=int(tl_obj["fee"]),
            storage_fee=int(tl_obj["storage_fee"]),
            other_fee=int(tl_obj["other_fee"]),
            in_msg=(
                Message.build(tl_obj.get("in_msg")) if tl_obj.get("in_msg") else None
            ),
            out_msgs=[Message.build(m) for m in tl_obj["out_msgs"]],
        )


class RawTransaction(GenericModel, Generic[ResultT]):
    type: Literal["raw.transaction"] = Field(alias="@type")
    address: Address
    utime: int
    data: str
    transaction_id: ResultT
    fee: int
    storage_fee: int
    other_fee: int
    in_msg: Optional[Message]
    out_msgs: List[Message]


class ShortTransaction(BaseModel):
    type: Literal["blocks.shortTxId"] = Field(alias="@type")
    mode: int
    account: str
    lt: str
    hash: str


class ShortTransactions(BaseModel):
    type: Literal["blocks.transactions"] = Field(alias="@type")
    id: BlockId
    req_count: int
    incomplete: bool
    transactions: List[ShortTransaction]


class TVMCell(BaseModel):
    type: Literal["tvm.cell"] = Field(alias="@type")
    bytes: str


class ConfigInfo(BaseModel):
    type: Literal["configInfo"] = Field(alias="@type")
    config: TVMCell
    extra: str = Field(alias="@extra")


class TvmStackEntry(BaseModel):
    type: str = Field(alias="@type")


class TvmTuple(BaseModel):
    type: Literal["tvm.tuple"] = Field(alias="@type")
    elements: List[TvmStackEntry]


class BlockIdExt(BaseModel):
    type: Literal["smc.blockIdExt"] = Field(alias="@type")
    workchain: int
    shard: str
    seqno: int
    root_hash: str
    file_hash: str


TVMStackEntryType = Literal["cell", "slice", "num", "tuple", "list"]


class AccountState(BaseModel):
    type: str = Field(alias="@type")
    wallet_id: str
    seqno: int


class AddressShort(BaseModel):
    type: str = Field(alias="@type")
    account_address: str


class JettonContent(BaseModel):
    type: str = Field(alias="@type")

    class Data(BaseModel):
        image: str
        name: str
        symbol: str
        description: str
        decimals: str

    data: Data
