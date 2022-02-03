FROM ubuntu:20.04

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata
RUN apt-get install -y git python3 python3-pip

# python requirements
ADD infrastructure/requirements/token_bot.txt /tmp/requirements.txt
RUN python3 -m pip install -r /tmp/requirements.txt

# app
COPY . /usr/src/pytonv3
WORKDIR /usr/src/pytonv3

# entrypoint
ENTRYPOINT [ "python3", "-m", "botTON" ]
