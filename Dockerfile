FROM swr.cn-north-4.myhuaweicloud.com/cj-docker/cangjie_ubuntu22_x86_kernel:v1.2 AS dev

# GNUStep setup
RUN bash -c "$(curl -fsSL https://raw.githubusercontent.com/plaurent/gnustep-build/refs/heads/master/ubuntu-22.04-clang-14.0-runtime-2.1/GNUstep-buildon-ubuntu2204.sh)"

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev

# Setup environment
RUN echo 'export OPENSSL_PATH=/usr/lib/x86_64-linux-gnu' >> "$HOME"/.bashrc && \
  echo 'export LD_LIBRARY_PATH="$OPENSSL_PATH":"$LD_LIBRARY_PATH"' >> "$HOME"/.bashrc && \
  echo 'export PATH=/usr/lib/llvm-15/bin:"$PATH"' >> "$HOME"/.bashrc && \
  echo 'export ARCH=x86_64' >> "$HOME"/.bashrc && \
  echo 'export SDK_NAME=linux-x64' >> "$HOME"/.bashrc && \
  echo 'export CANGJIE_VERSION=1.0.0' >> "$HOME"/.bashrc && \
  echo 'export STDX_VERSION=1' >> "$HOME"/.bashrc && \
  echo 'source /usr/GNUstep/System/Library/Makefiles/GNUstep.sh' >> "$HOME"/.bashrc && \
  echo 'source /home/cjdev/Projects/cangjie/envsetup.sh' >> "$HOME"/.bashrc && \
  echo 'if [[ -f /home/cjdev/Projects/dist/envsetup.sh ]]; then source /home/cjdev/Projects/dist/envsetup.sh; fi'>> "$HOME"/.bashrc
