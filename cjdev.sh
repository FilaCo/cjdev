#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

# absolute path of a workspace directory on host machine
CJDEV_HOST_WORKDIR=/home/filaco/Projects/cjdev
# absolute path of a workspace directory in a container
CJDEV_CONTAINER_WORKDIR=/home/cjdev/Projects
CJDEV_VERSION="$(<"$CJDEV_HOST_WORKDIR"/VERSION)"

# TODO: TOML/JSON/XML config file
declare -A CJDEV_ORIGINS=(
  [cangjie_compiler]='https://gitcode.com/filaco/cangjie_compiler.git'
  [cangjie_multiplatform_interop]='https://gitcode.com/filaco/cangjie_multiplatform_interop.git'
  [cangjie_runtime]='https://gitcode.com/filaco/cangjie_runtime.git'
  [cangjie_stdx]='https://gitcode.com/filaco/cangjie_stdx.git'
  [cangjie_test]='https://gitcode.com/filaco/cangjie_test.git'
  [cangjie_test_framework]='https://gitcode.com/filaco/cangjie_test_framework.git'
  [cangjie_tools]='https://gitcode.com/filaco/cangjie_tools.git'
)
declare -A CJDEV_UPSTREAMS=(
  [cangjie_compiler]='https://gitcode.com/Cangjie/cangjie_compiler.git'
  [cangjie_multiplatform_interop]='https://gitcode.com/Cangjie/cangjie_multiplatform_interop.git'
  [cangjie_runtime]='https://gitcode.com/Cangjie/cangjie_runtime.git'
  [cangjie_stdx]='https://gitcode.com/Cangjie/cangjie_stdx.git'
  [cangjie_test]='https://gitcode.com/Cangjie/cangjie_test.git'
  [cangjie_test_framework]='https://gitcode.com/Cangjie/cangjie_test_framework.git'
  [cangjie_tools]='https://gitcode.com/Cangjie/cangjie_tools.git'
)

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
  if [[ "$#" -eq 0 ]]; then
    set -- --help
  fi
  local prev_opt=
  while [[ "$#" -gt 0 ]]; do
    local arg="$1"
    shift
    case "$arg" in
    -h | --help)
      help_requested=true
      ;;
    -V | --version)
      cjdev::version
      ;;
    --)
      break
      ;;
    -*)
      cmd_opts+=("$arg")
      prev_opt=true
      ;;
    *)
      if [[ "$prev_opt" == true ]]; then
        cmd_opts+=("$arg")
        prev_opt=false
      else
        cmd_positionals+=("$arg")
      fi
      ;;
    esac
  done

  # if `--` is met - push the remainder as cmd_opts
  while [[ "$#" -gt 0 ]]; do
    cmd_opts+=("$1")
    shift
  done
}

cjdev() {
  local help_requested=
  local cmd_positionals=()
  local cmd_opts=()

  cjdev::getopt "$@"
  if [[ "${#cmd_positionals[@]}" -eq 0 ]] && [[ "$help_requested" == true ]]; then
    cjdev::help
  fi

  local cmd="${cmd_positionals[0]}"
  local positionals_len="${#cmd_positionals[@]}"
  local cmd_args=("${cmd_positionals[@]:1:$positionals_len}" "${cmd_opts[@]}")
  case "${cmd}" in
  i | init)
    init "${cmd_args[@]}"
    ;;
  build)
    build "${cmd_args[@]}"
    ;;
  git-mm)
    git-mm "${cmd_args[@]}"
    ;;
  dc)
    dc "${cmd_args[@]}"
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`$cmd\`" >&2
    cjdev::help
    ;;
  esac
}

cjdev "$@"
