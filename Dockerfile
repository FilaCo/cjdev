FROM swr.cn-north-4.myhuaweicloud.com/cj-docker/cangjie_ubuntu22_x86_kernel:v1.2 AS dev

# GNUStep setup
RUN bash -c "$(curl -fsSL https://raw.githubusercontent.com/plaurent/gnustep-build/refs/heads/master/ubuntu-22.04-clang-14.0-runtime-2.1/GNUstep-buildon-ubuntu2204.sh)"

RUN echo 'export OPENSSL_PATH=/usr/lib/x86_64-linux-gnu' >> /etc/profile && \
  echo 'export LD_LIBRARY_PATH="$OPENSSL_PATH":"$LD_LIBRARY_PATH"' >> /etc/profile && \
  echo 'export PATH=/usr/lib/llvm-15/bin:"$PATH"' >> /etc/profile && \
  echo 'export ARCH=x86_64' >> /etc/profile && \
  echo 'export SDK_NAME=linux-x64' >> /etc/profile && \
  echo 'export CANGJIE_VERSION=1.0.0' >> /etc/profile && \
  echo 'export STDX_VERSION=1' >> /etc/profile && \
  echo 'source /usr/GNUstep/System/Library/Makefiles/GNUstep.sh' >> /etc/profile && \
  echo 'source /home/cjdev/Projects/cangjie/envsetup.sh' >> /etc/profile && \
  echo 'if [[ -f /home/cjdev/Projects/dist/envsetup.sh ]]; then source /home/cjdev/Projects/dist/envsetup.sh; fi'>> /etc/profile

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev
