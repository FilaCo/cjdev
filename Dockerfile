FROM ubuntu:22.04 AS dev

RUN apt-get update && apt-get install -y \
  tar unzip wget curl libcurl4 expat openssl make gcc g++ gettext \
  nfs-common libtool sqlite3 zlib1g-dev libssl-dev cmake ninja-build\
  libcurl4-openssl-dev sudo autoconf build-essential rapidjson-dev \
  texinfo binutils expat libelf-dev libdwarf-dev openssh-client ssh \
  dos2unix libxext-dev libxtst-dev libxt-dev libcups2-dev clang clang-15 libedit-dev\
  libxrender-dev zip bzip2 libopenmpi-dev vim gdb lldb libclang-15-dev libgtest-dev\
  rpm patch libtinfo5 cpio rpm2cpio libncurses5 libncurses5-dev strace net-tools git;

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev
