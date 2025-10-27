FROM swr.cn-north-4.myhuaweicloud.com/cj-docker/cangjie_ubuntu22_x86_kernel:v1.2 AS dev

# Use huawei mirror source
RUN sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list;
RUN sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list;

RUN apt-get update && apt-get install -y \
  tar unzip wget curl libcurl4 expat openssl make gcc g++ gettext \
  nfs-common libtool sqlite3 zlib1g-dev libssl-dev ninja-build \
  libcurl4-openssl-dev sudo autoconf build-essential rapidjson-dev \
  texinfo binutils expat libelf-dev libdwarf-dev openssh-client ssh \
  dos2unix libxext-dev libxtst-dev libxt-dev libcups2-dev clang clang-15 libedit-dev \
  libxrender-dev zip bzip2 libopenmpi-dev vim gdb lldb libclang-15-dev libgtest-dev \
  rpm patch libtinfo5 cpio rpm2cpio libncurses5 libncurses5-dev strace net-tools git cmake;

# WORKDIR /tmp
# Install CMake
#RUN wget https://github.com/Kitware/CMake/releases/download/v4.2.0-rc1/cmake-4.2.0-rc1.tar.gz && \
#  tar -xzf cmake-4.2.0-rc1.tar.gz && \
#  cd cmake-4.2.0-rc1 && \
#  ./bootstrap && \
#  make -j$(nproc) && \
#  make install

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev
