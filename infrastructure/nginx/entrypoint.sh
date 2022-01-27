#!/bin/bash
set -e

certbot --nginx -d "test3.toncenter.com"
nginx -e stderr -g "daemon off;"
