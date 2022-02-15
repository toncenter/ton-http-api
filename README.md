# TON HTTP API

HTTP API for libtonlibjson (Telegram Open Network Light Client).

## Building and running

- The service is built and started with `toncenter.py` which under the hood is a proxy to `docker-compose` that reads `settings.yaml` file and calls `docker-compose` with correct arguments and environment variables.
#### Usage:

```
./toncenter.py [-s SETTINGS_FILE] action [ARGS]

Options:
  -s, --settings  Path to yaml settings file. Default: settings.yaml
  action          Command passed to docker-compose
```

- Quick start:
  - First time: run `./setup.sh` to install required building tools.
  - Configure `settings.yaml`. It controls such parameters as domain name, switch testnet/mainnet, enable db for logs, cache, rate limitting, etc (see [Configuration](#Configuration))
  - Build services: `./toncenter.py build`.
  - Run services: `./toncenter.py up -d`.
  - (Optional) Generate SSL certificates: 
    - Connect to nginx container and run CertBot: `./toncenter.py exec nginx certbot --nginx`.
    - Enter email, agree with EULA, choose DNS name and setup SSL certs.
    - Restart NGINX: `./toncenter.py restart nginx`.

## Configuration
The service consists of following components:
- **pyTON** - HTTP API to tonlibjson.
- **nginx** - handles domains, SSL certificates and sets up reverse proxy to pyTON.
- **logs** - saving requests and responses to db for analytics.
- **cache** - caching lite server responses.
- **ratelimit** - handles rate limiting and issuing API keys.

Each component has its settings in corresponding section in `settings.yaml`. See `settings.yaml` for detailed description of each parameter.

## Update tonlibjson library
- (Optional) Set commit hash in script `infrastructure/scripts/build_tonlib.sh` (line `RUN cd /ton && git checkout <...>`).
- Run script.
