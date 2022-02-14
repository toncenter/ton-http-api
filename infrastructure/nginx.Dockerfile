FROM nginx:latest

ARG LOCAL
ARG INDEX_FOLDER

RUN rm -rf /usr/share/nginx/html/*
RUN apt update --yes
RUN apt install --yes certbot python3-certbot-nginx python3-pip

RUN python3 -m pip install jinja2 pyyaml
COPY infrastructure/nginx/ /usr/src/
ADD config/settings.yaml /usr/src/settings.yaml
RUN /usr/src/gen_config.py /usr/src/settings.yaml /usr/src/nginx.jinja.conf /etc/nginx/nginx.conf

ADD $INDEX_FOLDER /usr/share/nginx/html

ENTRYPOINT [ "nginx", "-g", "daemon off;" ]
