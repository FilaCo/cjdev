#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

# absolute path of a workspace directory on host machine
HOST_WORKDIR=/home/filaco/Projects/cjdev
# absolute path of a workspace directory in a container
CONTAINER_WORKDIR=/home/cjdev/Projects
CJDEV_NAME="$0"
CJDEV_VERSION="$(<"$HOST_WORKDIR"/VERSION)"

source "$HOST_WORKDIR/src/util/ansi.sh"

cjdev::usage() {
  echo -e "$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$CJDEV_NAME [OPTIONS] [COMMAND]$(ansi::resetFg)"
}

cjdev::help::all() {
  echo -e "Cangjie's developer util script

$(cjdev::usage)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-V, --version$(ansi::resetFg)  Print version info and exit
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)build$(ansi::resetFg)    Build Cangjie's projects
  $(ansi::cyan)git-mm$(ansi::resetFg)   Git utils for Cangjie's repositories management

See '$(ansi::cyan)$CJDEV_NAME help <command>$(ansi::resetFg)' for more information on a specific command."
  exit 1
}

cjdev::help() {
  while true; do
    case "$1" in
    'build')
      cjdev::build::help
      ;;
    'git-mm')
      cjdev::git-mm::help
      ;;
    *)
      cjdev::help::all
      ;;
    esac
  done
}

cjdev::version() {
  echo "$0 $CJDEV_VERSION"
  exit 0
}

cjdev() {
  local p
  p="$(getopt -q -o Vh -l help,version -n "$0" -- "$@")"

  eval set -- "$p"
  while true; do
    case "$1" in
    -V | --version)
      cjdev::version
      ;;
    --)
      shift
      break
      ;;
    *)
      shift
      ;;
    esac
  done

  [ "$#" = 0 ] && cjdev::help::all

  local cmd="$1"
  eval set -- "$p"
  while true; do
    case "$cmd" in
    build)
      cjdev::build "$@"
      ;;
    git-mm)
      cjdev::git-mm "$@"
      ;;
    help)
      cjdev::help "$@"
      ;;
    *)
      #TODO:: to error report utils
      echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`$cmd\`" >&2
      cjdev::usage
      exit 1
      ;;
    esac
  done
}

cjdev "$@"
