# The environment a containerised `cjdev build` runs in.
#
# cjdev's own image rather than one pulled from a registry: the environment is
# a thing this repository defines, and a published image would be a second
# place for it to drift. The tag carries the hash of this file, so an edit to
# it cannot be shadowed by an image built from the version before.
#
# Ubuntu 22.04 rather than upstream's 18.04, which is EOL, and rather than
# 24.04, which has dropped three packages the list below needs: clang-15,
# libtinfo5 and libncurses5.
FROM ubuntu:22.04

# The package list is cangjie_build's own, from docs/linux.md 2.2, minus the
# editors, debuggers and remote tooling (vim, gdb, lldb, strace, net-tools,
# nfs-common, ssh) that a build never invokes, and minus sudo, which a
# container running as the caller's uid cannot use anyway.
#
# Three additions, and they are the ones upstream does not need:
#   python3    every build unit is `python3 build.py`, and the base has none;
#   ccache     nothing upstream mentions it, so cjdev supplies the launcher;
#   git        cjpm's build clones libuv, which is why ca-certificates is here
#              too and why the container needs network egress.
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --no-install-recommends --yes \
        autoconf \
        binutils \
        build-essential \
        bzip2 \
        ca-certificates \
        ccache \
        clang \
        clang-15 \
        cmake \
        cpio \
        curl \
        expat \
        gcc \
        g++ \
        gettext \
        git \
        libclang-15-dev \
        libcups2-dev \
        libcurl4 \
        libcurl4-openssl-dev \
        libdwarf-dev \
        libedit-dev \
        libelf-dev \
        libgtest-dev \
        libncurses5 \
        libncurses5-dev \
        libopenmpi-dev \
        libssl-dev \
        libtinfo5 \
        libtool \
        libxext-dev \
        libxrender-dev \
        libxt-dev \
        libxtst-dev \
        make \
        ninja-build \
        openssl \
        patch \
        python3 \
        rapidjson-dev \
        rpm \
        sqlite3 \
        swig \
        tar \
        texinfo \
        unzip \
        wget \
        zip \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# cangjie_build's convention for anything installed by hand. Nothing puts
# tooling here yet; the directory and the PATH entry exist so that whatever
# does lands where the guide says it does.
RUN mkdir -p /opt/buildtools/bin
ENV PATH="/opt/buildtools/bin:${PATH}"

# How the image describes itself. cjdev reads this with `image inspect`, from
# the host, so it never has to start a container to find out what is inside
# one - which is what lets `--dry-run` plan a containerised build honestly.
LABEL dev.cjdev.ccache="/usr/bin/ccache"

# No USER and no HOME: cjdev passes --user so that what the build writes into
# the mounted workspace belongs to the caller, and -e HOME pointing inside the
# mount, because this image has no passwd entry for that uid.
