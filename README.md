![splash_http_api](https://user-images.githubusercontent.com/1449561/154847286-989a6c51-1615-45e1-b40f-aec7c13014fa.png)

# HTTP API for [The Open Network](https://ton.org)

Since TON nodes uses its own ADNL binary transport protocol, a intermediate service is needed for an HTTP connection.

TON HTTP API is such a intermediate service, receiving requests via HTTP, it accesses the lite servers of the TON network using `tonlibjson`.

You can use the ready-made [toncenter.com](https://toncenter.com) service or start your own instance.

## Building and running
  - First time: run `./setup.sh` to install required building tools: `docker`, `docker-compose`, `curl`.
  - Run `./configure.py`, it creates `.env` file used by `docker-compose` (see [Configuration](#Configuration))
  - Build services: `docker-compose build`.
  - Run services: `docker-compose up -d`.
  - (Optional) Generate SSL certificates: 
    - Connect to nginx container and run CertBot: `docker-compose exec nginx certbot --nginx`.
    - Enter email, agree with EULA, choose DNS name and setup SSL certs.
    - Restart NGINX: `docker-compose restart nginx`.
   - Stop services: `docker-compose down`. Run this command with`-v` flag to clear docker volumes (mongodb, nginx and ssl data).

## Configuration
The service supports the following environment variables for configuration. After changing any variable run `./configure.py` and rebuild the project.

- `TON_API_LOGS_ENABLED` *(default: 0)*

Enables logging all requests and lite servers response statistics to MongoDB for further analysis. If you enable this component, you have to put MongoDB password in `./private/mongodb_password` file without `\n`.

- `TON_API_CACHE_ENABLED` *(default: 0)*

Enables caching lite server responses with Redis.

- `TON_API_RATE_LIMIT_ENABLED` *(default: 0)*

Enables API keys for your API and limits maximum request rate. API keys are issued by the Telegram bot and stored in Redis. If you enable this component, you have to put your Telegram bots token in `./private/token_file` file without `\n`.

- `TON_API_DOMAINS` *(default: localhost)*

List of domains separated by `:` which the service will use. Based on this list `nginx.conf` will be generated. For each domain `server` section will be added with specified `server_name`.

- `TON_API_INDEX_FOLDER` *(default: empty)*

Index page folder. All contents will be copied to the nginx html folder. If the variable is empty, index page is not used and redirects to `/api/v2`.

- `TON_API_ANALYTICS_ENABLED` *(default: 0)*

Enables `/analytics/` route providing useful endpoints for analytics. This features requires logs enabled.

- `TON_API_LITE_SERVER_CONFIG` *(default: config/mainnet.json)*

Path to config file with lite servers information.

- `TON_API_WEBSERVERS_WORKERS` *(default: 1)*

Number of webserver processes. If your server is under high load try increase this value to increase RPS. We recommend setting it to number of CPU cores / 2.

- `TON_API_GET_METHODS_ENABLED` *(default: 1)*

Enables `runGetMethod` endpoint.

- `TON_API_JSON_RPC_ENABLED` *(default: 1)*

Enables `jsonRPC` endpoint.

## FAQ
### How to point the service to my own lite server?

Copy `config/mainnet.json` and overwrite section `liteservers` with your liteserver. Assign `TON_API_LITE_SERVER_CONFIG` to path to your config, run `./configure.py` and rebuild the project.

### How to update tonlibjson library?

Set commit hash in `infrastructure/scripts/build_tonlib.sh` script (line `RUN cd /ton && git checkout <...>`) and run it. Docker container will get the sources, build the library and copy it to `pyTON/distlib/linux/`.
