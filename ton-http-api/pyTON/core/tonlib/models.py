from typing import Any, Optional
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
