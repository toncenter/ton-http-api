from typing import Optional, Union, Dict, Any, List
from pydantic import BaseModel


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
