#!/bin/bash
set -e

LOG_PATH=$(sudo docker inspect --format='{{.LogPath}}' $1)
mkdir -p logs
sudo cp $LOG_PATH logs/$1.log
sudo chmod +r logs/$1.log
