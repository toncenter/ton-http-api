from typing import Optional, Union, Dict, Any, List
from pydantic import BaseModel

from enum import Enum
from dataclasses import dataclass


@dataclass
class TonlibClientResult:
    task_id: str
    method: str
    elapsed_time: float
    params: Optional[Any] = None
    result: Optional[Any] = None
    exception: Optional[Exception] = None
    liteserver_info: Optional[Any] = None


class TonlibWorkerMsgType(Enum):
    TASK_RESULT = 0
    LAST_BLOCK_UPDATE = 1
    ARCHIVAL_UPDATE = 2


@dataclass
class ConsensusBlock:
    seqno: int = 0
    timestamp: int = 0


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
