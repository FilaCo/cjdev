FROM swr.cn-north-4.myhuaweicloud.com/cj-docker/cangjie_ubuntu22_x86_kernel:v1.2 AS dev

# GNUStep setup
RUN bash -c "$(curl -fsSL https://raw.githubusercontent.com/plaurent/gnustep-build/refs/heads/master/ubuntu-22.04-clang-14.0-runtime-2.1/GNUstep-buildon-ubuntu2204.sh)"

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev

RUN echo "source /usr/GNUstep/System/Library/Makefiles/GNUstep.sh" >> "$HOME/.bashrc"
