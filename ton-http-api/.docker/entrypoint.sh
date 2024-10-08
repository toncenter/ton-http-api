#!/bin/bash

set -e

echo "Running api with ${TON_API_WEBSERVERS_WORKERS:-1} workers"
echo "ENVIRONMENT:"
printenv

gunicorn -k uvicorn.workers.UvicornWorker -w ${TON_API_WEBSERVERS_WORKERS:-1} \
         --threads ${TON_API_WEBSERVERS_THREADS:-1} --bind 0.0.0.0:8081 ${TON_API_GUNICORN_FLAGS} pyTON.main:app
