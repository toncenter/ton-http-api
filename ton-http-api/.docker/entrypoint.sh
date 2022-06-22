#!/bin/bash

set -e

echo "Running api with ${TON_API_WEBSERVERS_WORKERS:-1} workers"
echo "ENVIRONMENT:"
printenv

gunicorn -k uvicorn.workers.UvicornWorker -w ${TON_API_WEBSERVERS_WORKERS:-1} --bind 0.0.0.0:8081 pyTON.main:app
