ARCH="$(uname -m)"

build::help() {
  echo -e "Cangjie's projects build commands

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 build [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-t$(ansi::resetFg), $(ansi::cyan)--build-type$(ansi::resetFg)    Target build type, defaults to release
  $(ansi::cyan)-h$(ansi::resetFg), $(ansi::cyan)--help$(ansi::resetFg)          Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)sdk$(ansi::resetFg)             Build all Cangjie's projects (default)
  $(ansi::cyan)compiler$(ansi::resetFg), $(ansi::cyan)cjc$(ansi::resetFg)   Build compiler
  $(ansi::cyan)runtime$(ansi::resetFg), $(ansi::cyan)rt$(ansi::resetFg)     Build runtime
  $(ansi::cyan)std$(ansi::resetFg)             Build standard library
  $(ansi::cyan)stdx$(ansi::resetFg)            Build standard library extensions
  $(ansi::cyan)tools$(ansi::resetFg)           Build all Cangjie's tools
  $(ansi::cyan)<tool_name>$(ansi::resetFg)     Build one of the tools (values: cjfmt, cjpm, lspserver)
  $(ansi::cyan)interop$(ansi::resetFg)         Build CJMP interop library."

  exit 1
}

build::cjc() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_compiler

  #dc python3 build.py clean
  dc python3 build.py build -t "$build_type" --no-tests
  dc python3 build.py install

  cd - >/dev/null

  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_compiler/output/* "$CJDEV_HOST_WORKDIR"/dist
}

build::rt() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_runtime/runtime

  #dc python3 build.py clean
  dc python3 build.py build -t "$build_type" -v '$CANGJIE_VERSION'
  dc python3 build.py install

  cd - >/dev/null

  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_runtime/runtime/output/common/linux_"$build_type"_"$ARCH"/{lib,runtime} "$CJDEV_HOST_WORKDIR"/dist
}

build::std() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_runtime/stdlib

  #dc python3 build.py clean
  dc python3 build.py build -t "$build_type" \
    --target-lib="$CJDEV_CONTAINER_WORKDIR"/cangjie_runtime/runtime/output \
    --target-lib='$OPENSSL_PATH'
  dc python3 build.py install

  cd - >/dev/null

  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_runtime/stdlib/output/* "$CJDEV_HOST_WORKDIR"/dist
}

build::stdx() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_stdx

  #dc python3 build.py clean
  dc python3 build.py build -t "$build_type" \
    --include="$CJDEV_CONTAINER_WORKDIR"/cangjie_compiler/include \
    --target-lib='$OPENSSL_PATH'
  dc python3 build.py install

  cd - >/dev/null
  
  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_stdx/target/* "$CJDEV_HOST_WORKDIR"/dist/third_party/stdx
}

build::tools() {
    build::tools::cjfmt
    build::tools::cjpm
    build::tools::lspserver
}

build::tools::cjfmt() {
    echo todo cjfmt
}

build::tools::cjpm() {

  cd "$CJDEV_HOST_WORKDIR"/cangjie_tools/cjpm/build

  local cangjie_stdx_path="$CJDEV_CONTAINER_WORKDIR"/cangjie_stdx/target/linux_${ARCH}_cjnative/static/stdx
  dc env CANGJIE_STDX_PATH="$cangjie_stdx_path"\
    python3 build.py build -t "$build_type" \
    --set-rpath \$ORIGIN/../../runtime/lib/linux_${ARCH}_cjnative
  dc python3 build.py install

  cd - >/dev/null
  
  rsync -a "$CJDEV_HOST_WORKDIR"/cangjie_tools/cjpm/dist/cjpm "$CJDEV_HOST_WORKDIR"/dist/tools/bin/cjpm
}

build::tools::lspserver() {
    echo todo lspserver
}

build::interop() {
  cd "$CJDEV_HOST_WORKDIR"/cangjie_multiplatform_interop/objc/build

  #dc python3 build.py clean
  dc python3 build.py build -t "$build_type" --target linux_"$ARCH"
  dc python3 build.py install --prefix "$CJDEV_HOST_WORKDIR"/dist --target linux_"$ARCH"

  cd - >/dev/null
}

build::getopt() {
  local p
  if ! p=$(getopt -o t: -l build-type: -n "$0" -- "$@"); then
    build::help
  fi

  eval set -- "$p"
  unset p
  while [[ "$#" -gt 0 ]]; do
    local opt="$1"
    shift
    case "$opt" in
    --)
      break
      ;;
    -t | --build-type)
      build_type="$1"
      shift
      ;;
    esac
  done

  if [[ -z "$build_type" ]]; then
    build_type=release
  fi

}

build() {
  if [[ "$help_requested" == true ]]; then
    build::help
  fi

  if [[ "$#" -eq 0 ]]; then
    set -- sdk
  fi

  local build_type=
  build::getopt "$@"

  local cmd="$1"
  case "$cmd" in
  cjc | compiler)
    build::cjc
    ;;
  rt | runtime)
    build::rt
    ;;
  std)
    build::std
    ;;
  stdx)
    build::stdx
    ;;
  interop)
    build::interop
    ;;
  sdk)
    build::cjc
    build::rt
    build::std
    build::stdx
    build::tools
    build::interop
    ;;
  tools)
    build::tools
    ;;
  cjfmt)
    build::tools::cjfmt
    ;;
  cjpm)
    build::tools::cjpm
    ;;
  lspserver)
    build::tools::lspserver
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: build \`$cmd\`" >&2
    build::help
    ;;
  esac
}
