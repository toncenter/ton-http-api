#!/bin/bash
set -e

docker-compose config | sed -E "s/cpus: ([0-9\\.]+)/cpus: '\\1'/"
