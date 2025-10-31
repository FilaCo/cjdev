#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

# absolute path of a workspace directory on host machine
HOST_WORKDIR=/home/filaco/Projects/cjdev
# absolute path of a workspace directory in a container
CONTAINER_WORKDIR=/home/cjdev/Projects
CJDEV_VERSION="$(<"$HOST_WORKDIR"/VERSION)"

source "$HOST_WORKDIR"/src/util/ansi.sh

source "$HOST_WORKDIR"/src/command/build.sh
source "$HOST_WORKDIR"/src/command/git-mm.sh
source "$HOST_WORKDIR"/src/command/dc.sh

cjdev::help::all() {
  echo -e "Cangjie's developer util script

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-V, --version$(ansi::resetFg)  Print version info and exit
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)build$(ansi::resetFg)    Build Cangjie's projects
  $(ansi::cyan)git-mm$(ansi::resetFg)   Git utils for Cangjie's repositories management
  $(ansi::cyan)dc$(ansi::resetFg)       Execute a command in a container

See '$(ansi::cyan)$0 help <command>$(ansi::resetFg)' for more information on a specific command."

  exit 1
}

cjdev::help() {
  [ "$#" -eq 0 ] && cjdev::help::all

  local cmd="$1"
  shift
  case "$cmd" in
  build)
    build::help "$@"
    ;;
  git-mm)
    git-mm::help "$@"
    ;;
  dc)
    dc::help "$@"
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`$cmd\`" >&2
    cjdev::help
    ;;
  esac
}

cjdev::version() {
  echo "$0 $CJDEV_VERSION"
  exit 0
}

cjdev::getopt() {
  [ "$#" -eq 0 ] && set -- help
  local p
  if ! p=$(getopt -o hV -l help,version -n "$0" -- "$@"); then
    cjdev::help
  fi

  eval set -- "$p"

  while [ "$#" -gt 0 ]; do
    local opt="$1"
    shift
    case "$opt" in
    --)
      break
      ;;
    -h | --help)
      cmd=help
      ;;
    -V | --version)
      cjdev::version
      ;;
    *)
      cmd_opts+=("$opt")
      ;;
    esac
  done

  if [ -z "$cmd" ]; then
    if [ "$#" -gt 0 ]; then
      cmd="$1"
      shift
    else
      cmd=help
    fi
  fi

  while [ "$#" -gt 0 ]; do
    cmd_opts+=("$1")
    shift
  done
}

cjdev() {
  local cmd=
  local cmd_opts=()

  cjdev::getopt "$@"

  case "$cmd" in
  help)
    cjdev::help "${cmd_opts[@]}"
    ;;
  build)
    build "${cmd_opts[@]}"
    ;;
  git-mm)
    git-mm "${cmd_opts[@]}"
    ;;
  dc)
    dc "${cmd_opts[@]}"
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`$cmd\`" >&2
    cjdev::help
    ;;
  esac
}

cjdev "$@"
