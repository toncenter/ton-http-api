FROM ubuntu:20.04

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata
RUN apt-get install -y git cmake wget python3 python3-pip

# python requirements
ADD deployment/requirements/main.txt /tmp/requirements.txt
RUN python3 -m pip install -r /tmp/requirements.txt

# app
COPY . /app
WORKDIR /app

# entrypoint
ENTRYPOINT [ "gunicorn", "pyTON.main:app", "-k", "uvicorn.workers.UvicornWorker" ]
