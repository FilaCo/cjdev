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

# GNUstep, for the objc-interoplib unit and for the ObjC interop tests that link
# against it (`gnustep-config --objc-flags` / `--base-libs`). Built from source
# because the interop calls libobjc2's API (`objc_msgSend`, `objc_retain`,
# `objc_autoreleasePoolPush`), and Ubuntu's gnustep-base is built on gcc's
# libobjc, which has none of it. Two runtimes in one process do not mix, so
# gnustep-base is rebuilt on libobjc2 too. gnustep-corebase is linked by some
# integration tests (`-lgnustep-corebase`); it has had no release since 2012, so
# it is pinned by commit, and built without GCD (libdispatch), which its configure
# otherwise demands and none of those tests use. Everything is pinned: a moving source is a different
# image under the same tag.
#
# `llvm-dev` is for the ObjCInteropGen unit: its Readme asks only for `clang`
# and `libclang-dev`, but their ClangConfig.cmake loads LLVMConfig.cmake.
ARG LIBOBJC2_TAG=v2.2.1
ARG GNUSTEP_MAKE_TAG=make-2_9_3
ARG GNUSTEP_BASE_TAG=base-1_31_1
ARG GNUSTEP_COREBASE_COMMIT=8117c092db139904ae08dc5d4b4b3c5553f2aa5a
RUN apt-get update && apt-get install --no-install-recommends --yes \
        libffi-dev \
        libgnutls28-dev \
        libicu-dev \
        libxml2-dev \
        libxslt1-dev \
        llvm-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /usr/src/gnustep && cd /usr/src/gnustep \
    && git clone --depth 1 --branch "${LIBOBJC2_TAG}" --recurse-submodules \
        --shallow-submodules https://github.com/gnustep/libobjc2.git \
    && cmake -S libobjc2 -B libobjc2/build -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DTESTS=OFF -DGNUSTEP_INSTALL_TYPE=NONE \
    && cmake --build libobjc2/build && cmake --install libobjc2/build && ldconfig \
    && git clone --depth 1 --branch "${GNUSTEP_MAKE_TAG}" \
        https://github.com/gnustep/tools-make.git \
    && (cd tools-make \
        && CC=clang CXX=clang++ ./configure --with-library-combo=ng-gnu-gnu \
            --with-runtime-abi=gnustep-2.2 \
        && make install) \
    && git clone --depth 1 --branch "${GNUSTEP_BASE_TAG}" \
        https://github.com/gnustep/libs-base.git \
    && (. "$(gnustep-config --variable=GNUSTEP_MAKEFILES)/GNUstep.sh" \
        && cd libs-base && ./configure && make -j"$(nproc)" && make install) \
    && ldconfig \
    && git clone https://github.com/gnustep/libs-corebase.git \
    && (cd libs-corebase && git checkout --quiet "${GNUSTEP_COREBASE_COMMIT}") \
    && (. "$(gnustep-config --variable=GNUSTEP_MAKEFILES)/GNUstep.sh" \
        && cd libs-corebase && ./configure --without-gcd \
        && make -j"$(nproc)" && make install) \
    && ldconfig \
    && cd / && rm -rf /usr/src/gnustep

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
