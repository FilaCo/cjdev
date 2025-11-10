# TODO: already set in containers .bashrc, remove this envs from that file if possible
OPENSSL_PATH=/usr/lib/x86_64-linux-gnu
ARCH=x86_64
SDK_NAME=linux-x64
CANGJIE_VERSION=1.0.0
STDX_VERSION=1

BUILD_MODE=debug

build::help() {
  echo "implement cjdev::build::help"
}

build::cjc() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_compiler

  #dc python3 build.py clean
  dc python3 build.py build -t "$BUILD_MODE" --no-tests
  dc python3 build.py install

  cd - >/dev/null

  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_compiler/output "$CJDEV_HOST_WORKDIR/dist"
}

build::rt() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_runtime/runtime

  #dc python3 build.py clean
  dc python3 build.py build -t "$BUILD_MODE" -v "$CANGJIE_VERSION"
  dc python3 build.py install

  cd - >/dev/null

  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_runtime/runtime/output/common/linux_"$BUILD_MODE"_"$ARCH"/{lib,runtime} "$CJDEV_HOST_WORKDIR"/dist
}

build::std() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_runtime/stdlib

  #dc python3 build.py clean
  dc python3 build.py build -t "$BUILD_MODE" \
    --target-lib="$CJDEV_CONTAINER_WORKDIR"/cangjie_runtime/runtime/output \
    --target-lib="$OPENSSL_PATH"
  dc python3 build.py install

  cd - >/dev/null

  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_runtime/stdlib/output/* "$CJDEV_HOST_WORKDIR"/dist
}

build::stdx() {
  echo todo stdx
}

build::interop() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_multiplatform_interop/objc/build

  #dc python3 build.py clean
  dc python3 build.py build -t "$BUILD_MODE" --target linux_"$ARCH"_cjnative
  dc python3 build.py install --prefix "$CJDEV_HOST_WORKDIR"/dist

  cd - >/dev/null
}

build() {
  if [[ "$#" -eq 0 ]]; then
    set -- all
  fi

  local cmd="$1"
  shift
  case "$cmd" in
  cjc | compiler)
    build::cjc "$@"
    ;;
  rt | runtime)
    build::rt "$@"
    ;;
  std)
    build::std "$@"
    ;;
  stdx)
    build::stdx "$@"
    ;;
  interop)
    build::interop "$@"
    ;;
  all)
    build::cjc
    build::rt
    build::std
    build::stdx
    build::interop
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: build \`$cmd\`" >&2
    build::help
    ;;
  esac
}
