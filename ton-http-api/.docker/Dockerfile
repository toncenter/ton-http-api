FROM ubuntu:22.04

RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get update && apt-get -y install tzdata
RUN apt-get update && apt-get install -y wget python3 python3-pip

# python requirements
ADD ./requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# app
COPY . /app
WORKDIR /app

# entrypoint
ENTRYPOINT [ "/bin/bash" ]
CMD [ "/app/.docker/entrypoint.sh" ]
