#!/bin/bash
set -e

echo "Setup Actions"
apt update --yes
apt install --yes curl

# install docker and compose
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && sh /tmp/get-docker.sh
curl -L "https://github.com/docker/compose/releases/download/v2.6.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Download the latest version of config.json
mkdir private

curl -sL https://ton-blockchain.github.io/global.config.json > private/mainnet.json
curl -sL https://ton-blockchain.github.io/testnet-global.config.json > private/testnet.json
