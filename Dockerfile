FROM swr.cn-north-4.myhuaweicloud.com/cj-docker/cangjie_ubuntu22_x86_kernel:v1.2 AS dev

RUN useradd -m -s /usr/bin/bash cjdev
USER cjdev

WORKDIR /home/cjdev
