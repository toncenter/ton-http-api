#!/bin/bash
set -e

docker stack deploy -c <(scripts/swarm_config.sh) ton-http-api
