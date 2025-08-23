FROM ubuntu:24.04 as tonlib-builder
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata

RUN apt install -y build-essential cmake clang openssl libssl-dev zlib1g-dev gperf wget \
    git curl libreadline-dev ccache libmicrohttpd-dev pkg-config \
    liblz4-dev libsodium-dev ninja-build autoconf libtool \
    automake libjemalloc-dev lsb-release software-properties-common gnupg

# build tonlib
WORKDIR /

# remove /tree/<commit> to build master branch
ARG TON_REPO
ARG TON_BRANCH
RUN git clone --recursive --branch ${TON_BRANCH:-master} https://github.com/${TON_REPO:-ton-blockchain/ton}
WORKDIR /ton

# fix lib version and patch logging
RUN mkdir /ton/build
WORKDIR /ton/build
ENV CC clang
ENV CXX clang++
RUN cmake -DPORTABLE=1 -DCMAKE_BUILD_TYPE=Release -DTON_ARCH= -DTON_USE_JEMALLOC=ON -GNinja ..
RUN ninja -j$(nproc) tonlibjson

FROM ubuntu:24.04

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata
RUN apt-get install -y git cmake wget python3 python3-pip curl \
    libsodium-dev libatomic1 openssl libmicrohttpd-dev liblz4-dev libjemalloc-dev

# python requirements
ADD ./requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r /tmp/requirements.txt

# app
COPY . /app
COPY --from=tonlib-builder /ton/build/tonlib/libtonlibjson.so /app/libtonlibjson.so

WORKDIR /app

# entrypoint
ENTRYPOINT [ "/bin/bash" ]
CMD [ "/app/.docker/entrypoint.sh" ]
