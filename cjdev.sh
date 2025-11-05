#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

# absolute path of a workspace directory on host machine
CJDEV_HOST_WORKDIR=/home/filaco/Projects/cjdev
# absolute path of a workspace directory in a container
CJDEV_CONTAINER_WORKDIR=/home/cjdev/Projects
CJDEV_VERSION="$(<"$CJDEV_HOST_WORKDIR"/VERSION)"

# TODO: TOML/JSON/XML config file
CJDEV_ORIGIN_CANGJIE_COMPILER_URL='https://gitcode.com/filaco/cangjie_compiler.git'
CJDEV_ORIGIN_CANGJIE_MULTIPLATFORM_INTEROP_URL='https://gitcode.com/filaco/cangjie_multiplatform_interop.git'
CJDEV_ORIGIN_CANGJIE_RUNTIME_URL='https://gitcode.com/filaco/cangjie_runtime.git'
CJDEV_ORIGIN_CANGJIE_STDX_URL='https://gitcode.com/filaco/cangjie_stdx.git'
CJDEV_ORIGIN_CANGJIE_TEST_URL='https://gitcode.com/filaco/cangjie_test.git'
CJDEV_ORIGIN_CANGJIE_TEST_FRAMEWORK_URL='https://gitcode.com/filaco/cangjie_test_framework.git'
CJDEV_ORIGIN_CANGJIE_TOOLS_URL='https://gitcode.com/filaco/cangjie_tools.git'

CJDEV_UPSTREAM_CANGJIE_COMPILER_URL='https://gitcode.com/Cangjie/cangjie_compiler.git'
CJDEV_UPSTREAM_CANGJIE_MULTIPLATFORM_INTEROP_URL='https://gitcode.com/Cangjie/cangjie_multiplatform_interop.git'
CJDEV_UPSTREAM_CANGJIE_RUNTIME_URL='https://gitcode.com/Cangjie/cangjie_runtime.git'
CJDEV_UPSTREAM_CANGJIE_STDX_URL='https://gitcode.com/Cangjie/cangjie_stdx.git'
CJDEV_UPSTREAM_CANGJIE_TEST_URL='https://gitcode.com/Cangjie/cangjie_test.git'
CJDEV_UPSTREAM_CANGJIE_TEST_FRAMEWORK_URL='https://gitcode.com/Cangjie/cangjie_test_framework.git'
CJDEV_UPSTREAM_CANGJIE_TOOLS_URL='https://gitcode.com/Cangjie/cangjie_tools.git'

source "$CJDEV_HOST_WORKDIR"/src/util/ansi.sh

source "$CJDEV_HOST_WORKDIR"/src/command/init.sh
source "$CJDEV_HOST_WORKDIR"/src/command/build.sh
source "$CJDEV_HOST_WORKDIR"/src/command/git-mm.sh
source "$CJDEV_HOST_WORKDIR"/src/command/dc.sh

cjdev::help() {
  echo -e "Cangjie's developer util script

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-V, --version$(ansi::resetFg)  Print version info and exit
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)init, i$(ansi::resetFg)  Init cjdev environment
  $(ansi::cyan)build$(ansi::resetFg)    Build Cangjie's projects
  $(ansi::cyan)git-mm$(ansi::resetFg)   Git utils for Cangjie's repositories management
  $(ansi::cyan)dc$(ansi::resetFg)       Execute a command in a container."

  exit 1
}

cjdev::version() {
  echo "$0 $CJDEV_VERSION"
  exit 0
}

cjdev::getopt() {
  [ "$#" -eq 0 ] && set -- --help
  while [ "$#" -gt 0 ]; do
    local arg="$1"
    shift
    case "$arg" in
    -h | --help)
      help_requested=true
      ;;
    -V | --version)
      cjdev::version
      ;;
    -*)
      cmd_opts+=("$arg")
      ;;
    *)
      cmd_positionals+=("$arg")
      ;;
    esac
  done
}

cjdev() {
  local help_requested=
  local cmd_positionals=()
  local cmd_opts=()

  cjdev::getopt "$@"
  if [ "${#cmd_positionals[@]}" -eq 0 ] && [ "$help_requested" == true ]; then
    cjdev::help
  fi

  local cmd="${cmd_positionals[0]}"
  unset "${cmd_positionals[0]}"
  local cmd_args="${cmd_positionals[*]}" -- "${cmd_opts[*]}"
  case "${cmd}" in
  i | init)
    init "$cmd_args"
    ;;
  build)
    build "$cmd_args"
    ;;
  git-mm)
    git-mm "$cmd_args"
    ;;
  dc)
    dc "$cmd_args"
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`$cmd\`" >&2
    cjdev::help
    ;;
  esac
}

cjdev "$@"
