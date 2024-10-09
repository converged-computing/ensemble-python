FROM fluxrm/flux-sched:jammy

LABEL maintainer="Vanessasaurus <@vsoch>"

# Match the default user id for a single system so we aren't root
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
ENV USERNAME=${USERNAME}
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}

# Pip not provided in this version
USER root
RUN apt-get update && apt-get install -y python3-pip
COPY requirements.txt /requirements.txt
COPY .github/dev-requirements.txt /dev-requirements.txt

RUN curl -OL https://github.com/protocolbuffers/protobuf/releases/download/v28.2/protoc-28.2-linux-x86_64.zip && \
    unzip -o protoc-28.2-linux-x86_64.zip -d /usr/local bin/protoc && \
    unzip -o protoc-28.2-linux-x86_64.zip -d /usr/local 'include/*' && \
    rm -f protoc-28.2-linux-x86_64.zip

# For easier Python development.
RUN python3 -m pip install IPython && \
    python3 -m pip install -r /requirements.txt
    python3 -m pip install -r /dev-requirements.txt

# Assuming installing to /usr/local
ENV LD_LIBRARY_PATH=/usr/local/lib

# extra interactive utilities and compilation_database generation
RUN apt-get update \
 && apt-get -qq install -y --no-install-recommends \
    vim \
    less && \
    ln -s $(which python3) /usr/bin/python

# Add the group and user that match our ids
RUN groupadd -g ${USER_GID} ${USERNAME} && \
    adduser --disabled-password --uid ${USER_UID} --gid ${USER_GID} --gecos "" ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers
USER $USERNAME
