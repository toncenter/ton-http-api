# pyTON

Python API for libtonlibjson (Telegram Open Network Light Client).
This project is loosely based on [formony ton_client](https://github.com/formony/ton_client)

## Running service
- First time: `./setup.sh`.
- Replace server_name in file `infrastructure/nginx.conf`.
- Set `liteserver_config` in `settings.yaml` to `testnet.json` or `mainnet.json`.
- Create file `private/mongodb_password` and put password there.
- Build services: `sudo docker-compose build`.
- Run services: `sudo docker-compose up -d`.
- Generate certs: 
    - Connect to nginx container and run CertBot: `sudo docker exec -it ton-http-api_nginx_1 certbot --nginx`.
    - Enter email, agree with EULA, choose DNS name and setup SSL certs.
    - Restart NGINX: `sudo docker-compose restart nginx`.

## Get logs from nginx
- Run script `infrastructure/scripts/get_container_logs.sh ton-http-api_<service-name-from-compose-file>_1`.

## Update library
- (Optional) Set commit in script `infrastructure/scripts/build_tonlib.sh` (line `RUN cd /ton && git checkout <...>`).
- Run script.
