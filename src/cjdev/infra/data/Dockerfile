# The environment a containerised `cjdev build` runs in.
#
# cjdev's own image rather than one pulled from a registry: the environment is
# a thing this repository defines, and a published image would be a second
# place for it to drift. The tag carries the hash of this file, so an edit to
# it cannot be shadowed by an image built from the version before.
#
# Ubuntu 24.04 rather than upstream's 18.04, which is EOL.
#
# The three packages 24.04 has dropped are ones this build does not need.
# `clang-15` and `libclang-15-dev` are pinned by upstream's list as the *host*
# compiler, not as anything the code links against: the compiler unit fetches
# `Cangjie/llvm-project` and builds LLVM from source
# (`cangjie_compiler/third_party/CMakeLists.txt`), so the version here only has
# to be able to compile it. `libtinfo5` and `libncurses5` are what a *prebuilt*
# LLVM wants, and there is no prebuilt LLVM here; 24.04's ncurses 6 development
# package stands in for `libncurses5-dev`.
FROM ubuntu:24.04

# The package list is cangjie_build's own, from docs/linux.md 2.2, minus the
# editors, debuggers and remote tooling (vim, gdb, lldb, strace, net-tools,
# nfs-common, ssh, openssh-client) that a build never invokes, minus sudo,
# which a container running as the caller's uid cannot use anyway, and minus
# dos2unix and rpm2cpio, which nothing in the build flow calls. The one of
# those with a near miss is ssh: `find_program(SSH_EXECUTABLE ssh)` in the
# compiler's `third_party/CMakeLists.txt` feeds a `GIT_CONFIG` sshCommand used
# only by the openharmony-repo branch, and even there over https. Its four
# version-pinned entries are unpinned for the reason above, and `libcurl4` is
# gone because `libcurl4-openssl-dev` pulls the runtime library under whatever
# name 24.04's time_t transition left it with.
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
        cmake \
        cpio \
        curl \
        expat \
        gcc \
        g++ \
        gettext \
        git \
        libclang-dev \
        libcups2-dev \
        libcurl4-openssl-dev \
        libdwarf-dev \
        libedit-dev \
        libelf-dev \
        libgtest-dev \
        libncurses-dev \
        libopenmpi-dev \
        libssl-dev \
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
