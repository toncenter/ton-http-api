from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi import Depends


# empty api key dependency for openapi schema
def api_key_dep(api_key_header: APIKeyHeader=Depends(APIKeyHeader(name='X-API-Key', auto_error=False)),
                api_key_query: APIKeyQuery=Depends(APIKeyQuery(name='api_key', auto_error=False))):
    pass
