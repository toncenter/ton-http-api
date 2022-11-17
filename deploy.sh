#!/bin/bash
set -e

export TONCENTER_ENV=${1:-stage}
echo "TONCENTER_ENV: ${TONCENTER_ENV}"

if [[ "${TONCENTER_ENV}" == "testnet" ]]; then
    echo "Using testnet config"
    export TON_API_TONLIB_LITESERVER_CONFIG=private/testnet.json
else
    echo "Using mainnet config"
    export TON_API_TONLIB_LITESERVER_CONFIG=private/mainnet.json
fi

export $(cat .env) > /dev/null|| echo "No .env file"

docker compose -f docker-compose.swarm.yaml build
docker compose -f docker-compose.swarm.yaml push

docker stack deploy -c docker-compose.swarm.yaml ${TONCENTER_ENV}
