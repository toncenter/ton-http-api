import os
import requests
import json

from typing import Optional
from dataclasses import dataclass
from loguru import logger


def strtobool(val):
    if val.lower() in ['y', 'yes', 't', 'true', 'on', '1']:
        return True
    if val.lower() in ['n', 'no', 'f', 'false', 'off', '0']:
        return False
    raise ValueError(f"Invalid bool value {val}")


@dataclass
class TonlibSettings:
    parallel_requests_per_liteserver: int
    keystore: str
    liteserver_config_path: str
    cdll_path: Optional[str] 
    request_timeout: int
    verbosity_level: int
    
    @property
    def liteserver_config(self):
        if not hasattr(self, '_liteserver_config'):
            if self.liteserver_config_path.startswith('https://') or self.liteserver_config_path.startswith('http://'):
                self._liteserver_config = requests.get(self.liteserver_config_path).json()
            else:
                with open(self.liteserver_config_path, 'r') as f:
                    self._liteserver_config = json.load(f)
        return self._liteserver_config

    @classmethod
    def from_environment(cls):
        verbosity_level = 0
        if os.environ.get('TON_API_LOGS_LEVEL') == 'DEBUG':
            verbosity_level = 4
        return TonlibSettings(parallel_requests_per_liteserver=int(os.environ.get('TON_API_TONLIB_PARALLEL_REQUESTS_PER_LITESERVER', '50')),
                              keystore=os.environ.get('TON_API_TONLIB_KEYSTORE', './ton_keystore/'),
                              liteserver_config_path=os.environ.get('TON_API_TONLIB_LITESERVER_CONFIG', 'https://ton.org/global-config.json'),
                              cdll_path=os.environ.get('TON_API_TONLIB_CDLL_PATH', None),
                              request_timeout=int(os.environ.get('TON_API_TONLIB_REQUEST_TIMEOUT', '10')),
                              verbosity_level=verbosity_level)


@dataclass
class RedisSettings:
    endpoint: str
    port: int
    timeout: Optional[int]=None

    @classmethod
    def from_environment(cls, settings_type):
        if settings_type == 'cache':
            return RedisSettings(endpoint=os.environ.get('TON_API_CACHE_REDIS_ENDPOINT', 'localhost'),
                                port=int(os.environ.get('TON_API_CACHE_REDIS_PORT', '6379')),
                                timeout=int(os.environ.get('TON_API_CACHE_REDIS_TIMEOUT', '1')))


@dataclass
class LoggingSettings:
    jsonify: bool
    level: str

    @classmethod
    def from_environment(cls):
        return LoggingSettings(jsonify=strtobool(os.environ.get('TON_API_LOGS_JSONIFY', '0')),
                               level=os.environ.get('TON_API_LOGS_LEVEL', 'WARNING'))


@dataclass
class CacheSettings:
    enabled: bool

    @classmethod
    def from_environment(cls):
        return CacheSettings(enabled=False)


@dataclass
class RedisCacheSettings(CacheSettings):
    redis: Optional[RedisSettings]

    @classmethod
    def from_environment(cls):
        return RedisCacheSettings(enabled=strtobool(os.environ.get('TON_API_CACHE_ENABLED', '0')),
                                  redis=RedisSettings.from_environment('cache'))


@dataclass
class WebServerSettings:
    api_root_path: str
    get_methods: bool
    json_rpc: bool

    @classmethod
    def from_environment(cls):
        return WebServerSettings(api_root_path=os.environ.get('TON_API_ROOT_PATH', '/'),
                                 get_methods=strtobool(os.environ.get('TON_API_GET_METHODS_ENABLED', '1')),
                                 json_rpc=strtobool(os.environ.get('TON_API_JSON_RPC_ENABLED', '1')))


@dataclass
class Settings:
    tonlib: TonlibSettings
    webserver: WebServerSettings
    cache: CacheSettings
    logging: LoggingSettings

    @classmethod
    def from_environment(cls):
        cache_enabled = strtobool(os.environ.get('TON_API_CACHE_ENABLED', '0'))
        logging = LoggingSettings.from_environment()
        cache = (RedisCacheSettings if cache_enabled else CacheSettings).from_environment()
        return Settings(tonlib=TonlibSettings.from_environment(),
                        webserver=WebServerSettings.from_environment(),
                        logging=logging,
                        cache=cache)
