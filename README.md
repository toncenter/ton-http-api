# TON HTTP API

HTTP API for libtonlibjson (Telegram Open Network Light Client).

## Building and running

- The service is built and started with `toncenter.py` which under the hood is a proxy to `docker-compose` that reads `settings.yaml` file and calls `docker-compose` with correct arguments and environment variables.
#### Usage:

```
./toncenter.py [-s SETTINGS_FILE] [COMMAND] [ARGS...]

Options:
  -s, --settings  Path to yaml settings file. Default: settings.yaml
Commands:
  build [--no-cache]   Build docker-compose images, 
                         --no-cache - Do not use cached images
  up                   Start service
  down [--volumes]     Stop service
                         --volumes - Clear all volumes (e.g. nginx data, mongodb with logs)
  ...                  Any command docker-compose supports.
```

- Quick start:
  - First time: run `./setup.sh` to install required building tools.
  - Configure `settings.yaml`. It controls such parameters as domain name, switch testnet/mainnet, enable db for logs, cache, rate limitting, etc (see [Configuration](#Configuration))
  - Build services: `./toncenter.py -s settings.yaml build`.
  - Run services: `./toncenter.py -s settings.yaml up`.
  - (Optional) Generate SSL certificates: 
    - Connect to nginx container and run CertBot: `./toncenter.py exec nginx certbot --nginx`.
    - Enter email, agree with EULA, choose DNS name and setup SSL certs.
    - Restart NGINX: `sudo docker-compose restart nginx`.

## Configuration
Configuration is possible by creating your own `settings.yaml` file. The service consists of following sections:
- **pyTON** - HTTP API to tonlibjson.
- **nginx** - handles domains, ssl certificates and sets up reverse proxy to pyTON.
- **logs** - logging requests to db for further analytics.
- **cache** - caching requests for faster response.
- **ratelimit** - handles rate limiting and issuing API keys.
See `settings.yaml` for detailed description of each field.

## Get container logs
- Run script `infrastructure/scripts/get_container_logs.sh ton-http-api_<service-name-from-compose-file>_1`.
- Logs will be copied to `./logs/ton-http-api_<service-name-from-compose-file>_1`

## Update tonlibjson library
- (Optional) Set commit hash in script `infrastructure/scripts/build_tonlib.sh` (line `RUN cd /ton && git checkout <...>`).
- Run script.
