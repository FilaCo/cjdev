FROM swr.cn-north-4.myhuaweicloud.com/cj-docker/cangjie_ubuntu22_x86_kernel:v1.2 AS dev

# GNUStep setup
RUN curl -fsSL "https://github.com/plaurent/gnustep-build/blob/master/ubuntu-22.04-clang-14.0-runtime-2.1/GNUstep-buildon-ubuntu2204.sh" | sh

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev
