FROM nginx:latest

ARG TON_API_HTTP_PORT
ARG TON_API_INDEX_FOLDER
ARG TON_API_DOMAINS
ARG TON_API_ANALYTICS_ENABLED

RUN rm -rf /usr/share/nginx/html/*
RUN apt update --yes
RUN apt install --yes certbot python3-certbot-nginx python3-pip

RUN python3 -m pip install jinja2
COPY infrastructure/nginx/ /usr/src/
RUN TON_API_HTTP_PORT=$TON_API_HTTP_PORT TON_API_INDEX_FOLDER=$TON_API_INDEX_FOLDER TON_API_DOMAINS=$TON_API_DOMAINS TON_API_ANALYTICS_ENABLED=$TON_API_ANALYTICS_ENABLED /usr/src/gen_config.py /usr/src/nginx.jinja.conf /etc/nginx/nginx.conf

ADD $TON_API_INDEX_FOLDER /usr/share/nginx/html

ENTRYPOINT [ "nginx", "-g", "daemon off;" ]
