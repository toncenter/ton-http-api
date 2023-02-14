#!/bin/bash
set -e

# toncenter env: stage, testnet, mainnet
export TONCENTER_ENV=${1:-stage}
STACK_NAME="${TONCENTER_ENV}-http-api"
echo "Stack: ${STACK_NAME}"

if [ -f ".env.${TONCENTER_ENV}" ]; then
    echo "Found env for ${TONCENTER_ENV}"
    ENV_FILE=".env.${TONCENTER_ENV}"
elif [ -f ".env" ]; then
    echo "Found default .env"
    ENV_FILE=".env"
fi

# load environment variables
if [ ! -z "${ENV_FILE}" ]; then
    # export $(cat ${ENV_FILE}) > /dev/null|| echo "No .env file"
    set -a
    source ${ENV_FILE}
    set +a
fi

if [[ "${TONCENTER_ENV}" == "testnet" ]]; then
    echo "Using testnet config"
    export TON_API_TONLIB_LITESERVER_CONFIG=private/testnet.json
elif [[ "${TONCENTER_ENV}" == "mainnet" || "${TONCENTER_ENV}" == "stage" ]]; then
    echo "Using mainnet config"
    export TON_API_TONLIB_LITESERVER_CONFIG=private/mainnet.json
else
    if [ -z "${TON_API_TONLIB_LITESERVER_CONFIG}" ]; then
        echo "Using custom env. Please parse custom liteserver to TON_API_TONLIB_LITESERVER_CONFIG"
        exit 1
    fi
fi

# build image
docker compose -f docker-compose.swarm.yaml build
docker compose -f docker-compose.swarm.yaml push

# deploy stack
docker stack deploy -c docker-compose.swarm.yaml ${STACK_NAME}
