import json
import redis
import secrets
from datetime import datetime
from fastapi import Request, Security
from fastapi.security.api_key import APIKeyQuery, APIKeyHeader, APIKey
from typing import Dict
from pymongo import MongoClient
from config import settings
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from limits import RateLimitItem, parse_many
from limits.errors import ConfigurationError
from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter

from pyTON.models import TonResponse

from loguru import logger

class APIKeyManager:
    def __init__(self, endpoint, port):
        self.r = redis.Redis(endpoint, port, decode_responses=True)

    def exists(self, api_key: str) -> bool:
        """
        Checks if api key exists in db

        :param api_key: API key to check
        """
        return self.r.exists(api_key)

    def get_limits(self, method: str, api_key: str) -> str:
        """
        Fetch limits for specific method and api key from db.

        :param method: Name of method to limit
        :param api_key: User's API key
        """
        result = self.r.get(api_key)
        if not result:
            return None
        result = json.loads(result)
        return result['limits'].get(method)

    def get_total_limits(self, api_key: str) -> str:
        """
        Fetch limits for all calls for api key from db.

        :param api_key: User's API key
        """
        result = self.r.get(api_key)
        if not result:
            return None
        result = json.loads(result)
        return result['limits'].get('total')

api_key_query = APIKeyQuery(name="api_key", description="API key sent as query parameter", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", description="API key sent as request header", auto_error=False)
default_total_limits_no_key = "1/second"
default_total_limits_with_key = "unlimited"
default_per_method_limits_no_key = "unlimited"
default_per_method_limits_with_key = "unlimited"
api_key_manager = APIKeyManager(settings.ratelimit.redis.endpoint, settings.ratelimit.redis.port)

def check_api_key(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header)
    ):
    api_key = api_key_query or api_key_header
    if api_key is None:
        return None
    if api_key_manager.exists(api_key):
        return api_key
    raise HTTPException(status_code=401, detail="API key does not exist.")

def per_method_limits(method: str, key: str):
    if not api_key_manager.exists(key):
        return default_per_method_limits_no_key
    limits = api_key_manager.get_limits(method, key)
    if limits is None:
        return default_per_method_limits_with_key
    return limits

def total_limits(key: str):
    if not api_key_manager.exists(key):
        return default_total_limits_no_key
    limits = api_key_manager.get_total_limits(key)
    if limits is None:
        return default_total_limits_with_key
    return limits

def get_referer(request: Request):
    url = request.headers.get('Referer') or request.headers.get('Origin')
    if url is None:
        return None
    url_parsed = urlparse(url)

    # Exclude toncenter host
    self_url = urlparse(request.url._url)
    if url_parsed.hostname == self_url.hostname:
        return None

    return url_parsed.hostname

def get_remote_address(request: Request):
    return request.headers.get('x-real-ip', "127.0.0.1")

def api_key_from_request(request: Request):
    api_key = check_api_key(request.query_params.get(api_key_query.model.name), request.headers.get(api_key_header.model.name))
    if api_key:
        return api_key
    referer = get_referer(request)
    if referer:
        return [get_referer(request), get_remote_address(request)]
    return get_remote_address(request)
