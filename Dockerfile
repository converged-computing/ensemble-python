FROM ubuntu:latest AS base

# docker build -t ghcr.io/converged-computing/ensemble-service .
RUN apt-get update && apt-get install -y \
    wget git vim build-essential iputils-ping postgresql-client curl \
    python3-pip unzip

# Install Go
ENV GO_VERSION=1.22.5
RUN wget https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz  && tar -xvf go${GO_VERSION}.linux-amd64.tar.gz && \
         mv go /usr/local && rm go${GO_VERSION}.linux-amd64.tar.gz

RUN PB_REL="https://github.com/protocolbuffers/protobuf/releases" && \
    curl -LO $PB_REL/download/v25.1/protoc-25.1-linux-x86_64.zip && \
    unzip protoc-25.1-linux-x86_64.zip -d /usr/local

ENV PATH=$PATH:/usr/local/go/bin
WORKDIR /code
COPY . .

RUN python3 -m pip install --break-system-packages -r requirements.txt && \
    ln -s $(which python3) /usr/bin/python && make && \
    python3 -m pip install --break-system-packages  -e .

# ensemble-server start --workers 10 --port <port>
ENTRYPOINT ["ensemble-server"]
CMD ["start"]
