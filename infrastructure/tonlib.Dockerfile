FROM ubuntu:20.04

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata

RUN apt install -y build-essential cmake clang-6.0 openssl libssl-dev zlib1g-dev gperf wget git curl libreadline-dev ccache libmicrohttpd-dev

# build tonlib
WORKDIR /

# remove /tree/<commit> to build master branch
RUN git clone --recurse-submodules https://github.com/newton-blockchain/ton.git

# fix lib version and patch logging
WORKDIR /ton
RUN git checkout 9875f02ef4ceba5b065d5e63c920f91aec73224e
COPY infrastructure/patches/tonlib.patch /ton/
RUN git apply /ton/tonlib.patch
RUN cat /ton/crypto/smc-envelope/SmartContract.h

RUN mkdir /ton/build
WORKDIR /ton/build
ENV CC clang-6.0
ENV CXX clang++-6.0
RUN cmake -DCMAKE_BUILD_TYPE=Release ..
RUN cmake --build . -j$(nproc) --target tonlibjson
