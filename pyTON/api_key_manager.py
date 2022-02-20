import json
import redis
from typing import Optional
from fastapi import Request, Security
from fastapi.security.api_key import APIKeyQuery, APIKeyHeader
from fastapi.exceptions import HTTPException
from urllib.parse import urlparse
from config import settings


class APIKeyManager:
    def __init__(self, endpoint, port):
        self.r = redis.Redis(endpoint, port, decode_responses=True)

    def exists(self, api_key: str) -> bool:
        """
        Checks if api key exists in db

        :param api_key: API key to check
        """
        return self.r.exists(api_key)

    def get_limits(self, method: str, api_key: str) -> Optional[str]:
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

    def get_total_limits(self, api_key: str) -> Optional[str]:
        """
        Fetch limits for all calls for api key from db.

        :param api_key: User's API key
        """
        result = self.r.get(api_key)
        if not result:
            return None
        result = json.loads(result)
        return result['limits'].get('total')

    def get_allowed_ips_and_origins(self, api_key: str):
        """
        Fetch allowed remote IPs and Origins for api key.

        :param api_key: User's API key
        """
        result = self.r.get(api_key)
        if not result:
            return None
        result = json.loads(result)
        return (result['ips'], result['domains'])

api_key_query = APIKeyQuery(name="api_key", description="API key sent as query parameter", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", description="API key sent as request header", auto_error=False)
default_total_limits_no_key = "1/second"
default_total_limits_with_key = "unlimited"
default_per_method_limits_no_key = "unlimited"
default_per_method_limits_with_key = "unlimited"
api_key_manager = APIKeyManager(settings.ratelimit.token_redis.endpoint, settings.ratelimit.token_redis.port)

def check_api_key(
    request: Request,
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header)
    ):
    api_key = api_key_query or api_key_header
    if api_key is None:
        return None

    if api_key_manager.exists(api_key):
        allowed_ips, allowed_origins = api_key_manager.get_allowed_ips_and_origins(api_key)

        if len(allowed_ips):
            if get_remote_address(request) not in allowed_ips:
                raise HTTPException(status_code=403, detail="Remote address not allowed.")

        if len(allowed_origins):
            origin = request.headers.get('Origin')
            if origin and origin not in allowed_origins:
                raise HTTPException(status_code=403, detail="Origin not allowed.")

        return api_key

    raise HTTPException(status_code=401, detail="API key does not exist.")

def is_referer_whitelisted(referer: str):
    if referer is None:
        return False
    return api_key_manager.exists(referer)

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

def get_referer_origin_key(request: Request):
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
    api_key = check_api_key(request, request.query_params.get(api_key_query.model.name), request.headers.get(api_key_header.model.name))
    if api_key:
        return api_key

    referer = get_referer_origin_key(request)
    if referer:
        if is_referer_whitelisted(referer):
            return referer
        return [referer, get_remote_address(request)]

    return get_remote_address(request)
