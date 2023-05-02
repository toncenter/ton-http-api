#!/bin/bash
set -e

mkdir -p private

# Downloading config files
wget https://ton.org/global-config.json -q -O private/mainnet.json  # mainnet config
wget https://ton-blockchain.github.io/testnet-global.config.json -q -O private/testnet.json # testnet config


if [[ $# -eq 1 ]]; then
    echo "Setting liteserver config for $1 network"
    TON_API_TONLIB_LITESERVER_CONFIG=private/$1.json
fi

function strtobool () {
    local ARG=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    case $ARG in 
        y|yes|t|true|on|1)
            echo "1"
            ;;
        n|no|f|false|off|0)
            echo "0"
            ;;
        *) echo "Err: Unknown boolean value \"$1\"" 1>&2; exit 1 ;;
    esac
}

COMPOSE_FILE=docker-compose.yaml
TON_API_CACHE_ENABLED=$(strtobool ${TON_API_CACHE_ENABLED:-0})
if [[ $TON_API_CACHE_ENABLED -eq "1" ]]; then
    echo "Enabling cache"
    COMPOSE_FILE=${COMPOSE_FILE}:docker-compose.cache.yaml
fi

cat <<EOF > .env
TON_API_CACHE_ENABLED=$(strtobool ${TON_API_CACHE_ENABLED:-0})
TON_API_CACHE_REDIS_ENDPOINT=${TON_API_CACHE_REDIS_ENDPOINT:-cache_redis}
TON_API_CACHE_REDIS_PORT=${TON_API_CACHE_REDIS_PORT:-6379}
TON_API_CACHE_REDIS_TIMEOUT=${TON_API_CACHE_REDIS_TIMEOUT:-1}
TON_API_LOGS_JSONIFY=$(strtobool ${TON_API_LOGS_JSONIFY:-0})
TON_API_LOGS_LEVEL=${TON_API_LOGS_LEVEL:-ERROR}
TON_API_GET_METHODS_ENABLED=$(strtobool ${TON_API_GET_METHODS_ENABLED:-1})
TON_API_HTTP_PORT=${TON_API_HTTP_PORT:-80}
TON_API_JSON_RPC_ENABLED=$(strtobool ${TON_API_JSON_RPC_ENABLED:-1})
TON_API_ROOT_PATH=${TON_API_ROOT_PATH:-/}
TON_API_V3_ENABLED=$(strtobool ${TON_API_V3_ENABLED:-0})
TON_API_WEBSERVERS_WORKERS=${TON_API_WEBSERVERS_WORKERS:-1}
TON_API_TONLIB_LITESERVER_CONFIG=${TON_API_TONLIB_LITESERVER_CONFIG:-private/mainnet.json}
TON_API_TONLIB_KEYSTORE=${TON_API_TONLIB_KEYSTORE:-/tmp/ton_keystore/}
TON_API_TONLIB_PARALLEL_REQUESTS_PER_LITESERVER=${TON_API_TONLIB_PARALLEL_REQUESTS_PER_LITESERVER:-50}
TON_API_TONLIB_CDLL_PATH=${TON_API_TONLIB_CDLL_PATH}
TON_API_TONLIB_REQUEST_TIMEOUT=${TON_API_TONLIB_REQUEST_TIMEOUT:-10}
TON_API_GUNICORN_FLAGS="${TON_API_GUNICORN_FLAGS}"

COMPOSE_FILE=${COMPOSE_FILE}

DOCKER_REGISTRY=toncenter
DOCKER_REPO=ton-http-api
IMAGE_TAG=latest

DOCKERFILE=Dockerfile
TON_REPO=
TON_BRANCH=
EOF

echo
echo "Config file:"
cat .env
