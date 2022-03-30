#!/bin/bash
set -e

BACKUP_FILE=/var/ton-backups/tokenbot_redis_$1.rdb
echo "Copying Token BOT data to $BACKUP_FILE"
cp /home/toncenter/ton-http-api/private/botTON_data/dump.rdb $BACKUP_FILE
