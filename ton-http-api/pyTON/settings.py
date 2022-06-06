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
        return TonlibSettings(parallel_requests_per_liteserver=int(os.environ.get('TON_API_TONLIB_PARALLEL_REQUESTS_PER_LITESERVER', '50')),
                              keystore=os.environ.get('TON_API_TONLIB_KEYSTORE', './ton_keystore/'),
                              liteserver_config_path=os.environ.get('TON_API_TONLIB_LITESERVER_CONFIG', 'https://ton.org/global-config.json'),
                              cdll_path=os.environ.get('TON_API_TONLIB_CDLL_PATH', None),
                              request_timeout=int(os.environ.get('TON_API_TONLIB_REQUEST_TIMEOUT', '10')))


@dataclass
class MongoDBSettings:
    host: str
    port: int
    database: str
    username: Optional[str]
    password_file: Optional[str]

    @property
    def password(self):
        if self.password_file is None:
            return None
        try:
            with open(self.password_file, 'r') as f:
                return f.read()
        except Exception as ee:
            logger.error(f'Failed to read password from file: {ee}')
            return None

    @classmethod
    def from_environment(cls, settings_type):
        if settings_type == 'logging':
            return MongoDBSettings(host=os.environ.get('TON_API_LOGS_MONGODB_HOST', 'localhost'),
                                   port=int(os.environ.get('TON_API_LOGS_MONGODB_PORT', '27017')),
                                   database=os.environ.get('TON_API_LOGS_MONGODB_DATABASE', 'pyton'),
                                   username=os.environ.get('TON_API_LOGS_MONGODB_USERNAME', None),
                                   password_file=os.environ.get('TON_API_LOGS_MONGODB_PASSWORD_FILE', None))


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
    enabled: bool
    jsonify: bool
    log_successful_requests: bool
    record_ttl: int

    @classmethod
    def from_environment(cls):
        return LoggingSettings(enabled=False,
                               jsonify=False,
                               log_successful_requests=False,
                               record_ttl=86400)


@dataclass
class MongoDBLoggingSettings(LoggingSettings):
    mongodb: MongoDBSettings

    @classmethod
    def from_environment(cls):
        return MongoDBLoggingSettings(enabled=strtobool(os.environ.get('TON_API_LOGS_ENABLED', '0')),
                                      enabled=strtobool(os.environ.get('TON_API_LOGS_JSONIFY', '0')),
                                      log_successful_requests=strtobool(os.environ.get('TON_API_LOGS_LOG_SUCCESSFUL', '0')),
                                      record_ttl=86400,
                                      mongodb=MongoDBSettings.from_environment('logging'))


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
    logging: LoggingSettings
    cache: CacheSettings

    @classmethod
    def from_environment(cls):
        loggging_enabled = strtobool(os.environ.get('TON_API_LOGS_ENABLED', '0'))
        cache_enabled = strtobool(os.environ.get('TON_API_CACHE_ENABLED', '0'))

        logging = (MongoDBLoggingSettings if loggging_enabled else LoggingSettings).from_environment()
        cache = (RedisCacheSettings if cache_enabled else CacheSettings).from_environment()
        return Settings(tonlib=TonlibSettings.from_environment(),
                        webserver=WebServerSettings.from_environment(),
                        logging=logging,
                        cache=cache)
