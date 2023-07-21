FROM ubuntu:20.04 as tonlib-builder
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata

RUN apt install -y build-essential cmake clang openssl libssl-dev zlib1g-dev gperf wget git curl libreadline-dev ccache libmicrohttpd-dev pkg-config libsecp256k1-dev libsodium-dev ninja-build

# build tonlib
WORKDIR /

# remove /tree/<commit> to build master branch
ARG TON_REPO
ARG TON_BRANCH
RUN git clone --recurse-submodules https://github.com/${TON_REPO:-ton-blockchain/ton}
WORKDIR /ton
RUN git checkout ${TON_BRANCH:-master} && git submodule update --init --recursive

# fix lib version and patch logging
RUN mkdir /ton/build
WORKDIR /ton/build
ENV CC clang
ENV CXX clang++
RUN cmake -DCMAKE_BUILD_TYPE=Release .. -GNinja
RUN ninja -j$(nproc) tonlibjson

FROM ubuntu:20.04

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata
RUN apt-get install -y git cmake wget python3 python3-pip curl libsecp256k1-dev libsodium-dev

# python requirements
ADD ./requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# app
COPY . /app
COPY --from=tonlib-builder /ton/build/tonlib/libtonlibjson.so /app/libtonlibjson.so

WORKDIR /app

# entrypoint
ENTRYPOINT [ "/bin/bash" ]
CMD [ "/app/.docker/entrypoint.sh" ]
