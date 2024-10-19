FROM ubuntu:latest AS base

# docker build -t ghcr.io/converged-computing/ensemble-service .
RUN apt-get update && apt-get install -y \
    wget git vim build-essential iputils-ping postgresql-client curl \
    python3-pip unzip

# Or for arm: aarch_64
ARG ARCH=x86_64
ENV ARCH=${ARCH}

RUN PB_REL="https://github.com/protocolbuffers/protobuf/releases" && \
    curl -LO $PB_REL/download/v28.2/protoc-28.2-linux-${ARCH}.zip && \
    unzip protoc-28.2-linux-${ARCH}.zip -d /usr/local

WORKDIR /code
COPY . .

RUN python3 -m pip install --break-system-packages -r requirements.txt && \
    ln -s $(which python3) /usr/bin/python && make && \
    python3 -m pip install --break-system-packages  -e .

# ensemble-server start --workers 10 --port <port>
ENTRYPOINT ["ensemble-server"]
CMD ["start"]
