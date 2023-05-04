#!/bin/bash
set -e

# toncenter env: testnet, mainnet, stage
export TONCENTER_ENV=${1:-mainnet}
STACK_NAME="${TONCENTER_ENV}-http-api"
echo "Deploying stack: ${STACK_NAME}"

if [ -f ".env.${TONCENTER_ENV}" ]; then
    echo "Found env for ${TONCENTER_ENV}"
    ENV_FILE=".env.${TONCENTER_ENV}"
elif [ -f ".env" ]; then
    echo "Found default .env"
    ENV_FILE=".env"
fi

# load environment variables
if [ ! -z "${ENV_FILE}" ]; then
    set -a; source ${ENV_FILE}; set +a
fi

# check global network
NETWORK_ID=$(docker network ls -f "name=toncenter-global" -q)

if [[ -z "$NETWORK_ID" ]]; then
    echo "Creating toncenter-global network"
    NETWORK_ID=$(docker network create --attachable --driver=overlay toncenter-global)
fi
echo "Network ID of toncenter-global: $NETWORK_ID"

# build image
docker compose -f docker-compose.swarm.yaml build
docker compose -f docker-compose.swarm.yaml push

# deploy stack
docker stack deploy --with-registry-auth -c docker-compose.swarm.yaml ${STACK_NAME}
