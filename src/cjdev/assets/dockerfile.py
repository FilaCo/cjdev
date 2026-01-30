DOCKERFILE = r"""FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Moscow

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    libssl-dev \
    sudo \
    tzdata \
    wget

RUN set -eux; \
    wget -O- "https://cmake.org/files/v3.26/cmake-3.26.6-linux-x86_64.tar.gz" | \
    tar --strip-components=1 -xz -C /usr/local

# GNUStep setup
RUN set -eux; \
    bash -c "$(curl -fsSL https://raw.githubusercontent.com/plaurent/gnustep-build/refs/heads/master/ubuntu-22.04-clang-14.0-runtime-2.1/GNUstep-buildon-ubuntu2204.sh)"

# Install dependencies
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    tar unzip wget curl libcurl4 expat openssl make gcc g++ gettext \
    nfs-common libtool sqlite3 zlib1g-dev libssl-dev cmake ninja-build\
    libcurl4-openssl-dev sudo autoconf build-essential rapidjson-dev \
    texinfo binutils expat libelf-dev libdwarf-dev openssh-client ssh \
    dos2unix libxext-dev libxtst-dev libxt-dev libcups2-dev clang clang-15 libedit-dev\
    libxrender-dev zip bzip2 libopenmpi-dev vim gdb lldb libclang-15-dev libgtest-dev\
    rpm patch libtinfo5 cpio rpm2cpio libncurses5 libncurses5-dev strace net-tools \
    python3 python-is-python3;

# Install java interop deps
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    openjdk-17-jdk;

# Install custom packages
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    zsh

# Setup environment
RUN echo 'export OPENSSL_PATH=/usr/lib/x86_64-linux-gnu' >> /etc/profile && \
    echo 'export LD_LIBRARY_PATH="$OPENSSL_PATH":"$LD_LIBRARY_PATH"' >> /etc/profile && \
    echo 'export PATH=/usr/lib/llvm-15/bin:"$PATH"' >> /etc/profile && \
    echo 'export ARCH=x86_64' >> /etc/profile && \
    echo 'export SDK_NAME=linux-x64' >> /etc/profile && \
    echo 'export CANGJIE_VERSION=1.0.0' >> /etc/profile && \
    echo 'export STDX_VERSION=1' >> /etc/profile && \
    echo 'source /usr/GNUstep/System/Library/Makefiles/GNUstep.sh' >> /etc/profile && \
    echo 'export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64' >> /etc/profile && \
    echo 'if [[ -f /home/cjdev/cangjie/envsetup.sh ]]; then source /home/cjdev/cangjie/envsetup.sh; fi' >> /etc/profile && \
    echo 'if [[ -f /home/cjdev/dist/envsetup.sh ]]; then source /home/cjdev/dist/envsetup.sh; fi' >> /etc/profile

RUN useradd -m -s /usr/bin/zsh cjdev
USER cjdev

WORKDIR /home/cjdev
"""
