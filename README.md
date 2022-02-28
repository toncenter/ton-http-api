![splash_http_api](https://user-images.githubusercontent.com/1449561/154847286-989a6c51-1615-45e1-b40f-aec7c13014fa.png)

# HTTP API for [The Open Network](https://ton.org)

Since TON nodes uses its own ADNL binary transport protocol, a intermediate service is needed for an HTTP connection.

TON HTTP API is such a intermediate service, receiving requests via HTTP, it accesses the lite servers of the TON network using `tonlibjson`.

You can use the ready-made [toncenter.com](https://toncenter.com) service or start your own instance.

## Building and running

Tested on Ubuntu 18.04 and Intel MacOS Catalina/Big Sur but it should work even on Windows.

Does not work on the Apple M1 yet.

Recommended hardware: 2 CPU, 8 GB RAM.

  - First time: run `./setup.sh` to install required building tools: `docker`, `docker-compose`, `curl`.
  - Run `./configure.py`, it creates `.env` file used by `docker-compose` (see [Configuration](#Configuration))
  - Build services: `docker-compose build`.
  - Run services: `docker-compose up -d`.
  - (Optional) Generate SSL certificates: 
    - Make sure you set `TON_API_DOMAINS` and `TON_API_SSL_ENABLED` environment variables.
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

- `TON_API_SSL_ENABLED` *(default: 0)*

    Enables exposing port 443 for SSL connection. To setup SSL you have to set `TON_API_DOMAINS` and run the steps described in *Generate SSL certificates* section.

- `TON_API_HTTP_PORT` *(default: 80)*

    Port for HTTP connections that will be listened by Nginx. Since Certbot assumes HTTP is run on 80 any value other can lead to issues with setting up SSL.

- `TON_API_MONGODB_PORT` *(default: 27017)*

    Port for connecting to MongoDB with requests logs (see `TON_API_LOGS_ENABLED`).

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

- `TON_API_CLOUDFLARE_ENABLED` *(default: 0)*

    Configures Nginx to support Cloudflare CDN.

## FAQ
### How to point the service to my own lite server?

To point the HTTP API to your own lite server you should set `TON_API_LITE_SERVER_CONFIG` to config file with your only lite server.

- If you use MyTonCtrl on your node you can generate config file with these commands: 
    ```
    $ mytonctrl
    MyTonCtrl> installer
    MyTonInstaller> clcf
    ```
    Config file will be saved at `/usr/bin/ton/local.config.json`.
- If you don't use MyTonCtrl: copy `config/mainnet.json` and overwrite section `liteservers` with your liteservers ip, port and public key. To get public key from `liteserver.pub` file use the following script:
    ```
    python -c 'import codecs; f=open("liteserver.pub", "rb+"); pub=f.read()[4:]; print(str(codecs.encode(pub,"base64")).replace("\n",""))'
    ```
- Once config file is created assign variable `TON_API_LITE_SERVER_CONFIG` to its path, run `./configure.py` and rebuild the project.

### How to run multiple API instances on single machine?

- Clone the repo as many times as many instances you need to the folders with different names (otherwise docker-compose containers will conflict). 
- Configure each instance to have unique exposed ports (`TON_API_HTTP_PORT` and `TON_API_MONGODB_PORT`).
- Build and run every instance. 
- Note: only one instance is allowed to have SSL enabled.

### How to update tonlibjson library?

Set commit hash in `infrastructure/scripts/build_tonlib.sh` script (line `RUN cd /ton && git checkout <...>`) and run it. Docker container will get the sources, build the library and copy it to `pyTON/distlib/linux/`.
