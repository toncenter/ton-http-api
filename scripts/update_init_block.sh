#!/bin/bash

ENDPOINT=https://toncenter.com/api/v2


function usage() {
    echo 'required 1 positional argument: name of config file'
    echo 'Supported argumets:'
    echo ' -h --help                Show this message'
    echo '    --testnet             Use testnet endpoint'
    exit
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 1
            ;;
        --testnet)
            ENDPOINT=https://testnet.toncenter.com/api/v2
            shift
            ;;
        -*|--*)
            echo "Error: unknown option $1"
            usage
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1") # save positional arg
            shift # past argument
            ;;
    esac
done

set -- "${POSITIONAL_ARGS[@]}"

# main logic
LAST_SEQNO=$(curl -s ${ENDPOINT}/getMasterchainInfo | jq ".result.last.seqno")
echo "Last seqno is $LAST_SEQNO"

sleep 1
LAST_KEYBLOCK_SEQNO=$(curl -s "${ENDPOINT}/getBlockHeader?workchain=-1&shard=-9223372036854775808&seqno=${LAST_SEQNO}" | jq .result.prev_key_block_seqno)
echo "Last keyblock seqno is $LAST_KEYBLOCK_SEQNO"

sleep 1
RES=$(curl -s "${ENDPOINT}/lookupBlock?workchain=-1&shard=-9223372036854775808&seqno=${LAST_KEYBLOCK_SEQNO}" | jq .result )

SEQNO=$(echo "$RES" | jq '.seqno')
FILEHASH=$(echo "$RES" | jq '.file_hash')
ROOTHASH=$(echo "$RES" | jq '.root_hash')

FILENAME=$1

cp $FILENAME $FILENAME.bk || echo "Failed to backup the config"
python3 <<EOF
import json
with open("$FILENAME", 'r') as f:
    data = json.load(f)
data['validator']['init_block']['seqno'] = $SEQNO
data['validator']['init_block']['file_hash'] = $FILEHASH
data['validator']['init_block']['root_hash'] = $ROOTHASH

with open("$FILENAME", 'w') as f:
    json.dump(data, f, indent=4)
EOF
echo "Init block updated"
