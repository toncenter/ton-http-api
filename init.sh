#!/bin/bash
set -e

mkdir -p private

wget https://ton.org/global-config.json -q -O private/mainnet.json  # mainnet config
wget https://ton-blockchain.github.io/testnet-global.config.json -q -O private/testnet.json # testnet config
