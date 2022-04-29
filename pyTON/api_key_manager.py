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

class LimitKey:
    def __init__(self, api_key=None, origin=None, ip=None):
        assert api_key is not None or origin is not None or ip is not None
        self.api_key = api_key
        self.origin = origin
        self.ip = ip

    def __repr__(self):
        return f'{self.api_key}{self.origin}{self.ip}'

api_key_query = APIKeyQuery(name="api_key", description="API key sent as query parameter", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", description="API key sent as request header", auto_error=False)
default_total_limits_no_key = "1/second"
default_total_limits_with_key = "unlimited"
default_per_method_limits_no_key = "unlimited"
default_per_method_limits_with_key = "unlimited"
api_key_manager = APIKeyManager(settings.ratelimit.token_redis.endpoint, settings.ratelimit.token_redis.port)

# Dependency for FastAPI. Checks existance of API key in request.
def check_api_key(
    request: Request,
    api_key_query_str: str = Security(api_key_query),
    api_key_header_str: str = Security(api_key_header)
    ):
    api_key = api_key_query_str or api_key_header_str
    if api_key is None:
        return None

    if api_key_manager.exists(api_key):
        allowed_ips, allowed_origins = api_key_manager.get_allowed_ips_and_origins(api_key)

        if len(allowed_ips):
            if get_ip(request) not in allowed_ips:
                raise HTTPException(status_code=403, detail="Remote address not allowed.")

        if len(allowed_origins):
            origin = request.headers.get('Origin')
            if origin and origin not in allowed_origins:
                raise HTTPException(status_code=403, detail="Origin not allowed.")

        return api_key

    raise HTTPException(status_code=401, detail="API key does not exist.")

# Functions to get limits from LimitKey

def per_method_limits(method: str, key: LimitKey):
    lookup_key = None
    if key.api_key and api_key_manager.exists(key.api_key):
        lookup_key = key.api_key
    elif key.origin and api_key_manager.exists(key.origin):
        lookup_key = key.origin
    elif key.ip and api_key_manager.exists(key.ip):
        lookup_key = key.ip
    if lookup_key is None:
        return default_per_method_limits_no_key

    return api_key_manager.get_limits(method, lookup_key) or default_per_method_limits_with_key

def total_limits(key: LimitKey):
    lookup_key = None
    if key.api_key and api_key_manager.exists(key.api_key):
        lookup_key = key.api_key
    elif key.origin and api_key_manager.exists(key.origin):
        lookup_key = key.origin
    elif key.ip and api_key_manager.exists(key.ip):
        lookup_key = key.ip
    if lookup_key is None:
        return default_total_limits_no_key
    
    return api_key_manager.get_total_limits(lookup_key) or default_total_limits_with_key

# Functions to get LimitKey components

def get_origin(request: Request):
    url = request.headers.get('Origin')
    if url is None:
        return None
    url_parsed = urlparse(url)

    # Exclude toncenter host
    self_url = urlparse(request.url._url)
    if url_parsed.hostname == self_url.hostname:
        return None

    return f'{url_parsed.scheme}://{url_parsed.hostname}'

def get_ip(request: Request):
    return request.client.host or "127.0.0.1"

def get_api_key(request: Request):
    return check_api_key(request,
        request.query_params.get(api_key_query.model.name), 
        request.headers.get(api_key_header.model.name))

# Gets array of LimitKey from request. 
# Each element will be used for limitting endependently.
def limit_keys_from_request(request: Request):
    api_key = check_api_key(request, request.query_params.get(api_key_query.model.name), request.headers.get(api_key_header.model.name))
    origin = get_origin(request)
    if api_key:
        if origin:
            return [LimitKey(api_key=api_key, ip=get_ip(request))]
        return [LimitKey(api_key=api_key)]

    if origin:
        if is_origin_whitelisted(origin):
            return [LimitKey(origin=origin)]
        return [LimitKey(origin=origin), LimitKey(ip=get_ip(request))]

    return [LimitKey(ip=get_ip(request))]

def is_origin_whitelisted(origin: str):
    if origin is None:
        return False
    return api_key_manager.exists(origin)
