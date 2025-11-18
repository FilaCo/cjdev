#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

CJDEV_SCRIPTS_HOME=$(dirname "$(readlink -f "$0")")

source "$CJDEV_SCRIPTS_HOME"/.env

# absolute path of a workspace directory in a container
CJDEV_CONTAINER_WORKDIR=/home/cjdev/Projects
CJDEV_VERSION="$(<"$CJDEV_SCRIPTS_HOME"/VERSION)"

CJDEV_GIT_MM_CONFIG_FILE="$CJDEV_SCRIPTS_HOME"/.git-mm

source "$CJDEV_SCRIPTS_HOME"/src/util/ansi.sh
source "$CJDEV_SCRIPTS_HOME"/src/util/log.sh
source "$CJDEV_SCRIPTS_HOME"/src/util/gitcode.sh

source "$CJDEV_SCRIPTS_HOME"/src/command/init.sh
source "$CJDEV_SCRIPTS_HOME"/src/command/build.sh
source "$CJDEV_SCRIPTS_HOME"/src/command/git-mm.sh
source "$CJDEV_SCRIPTS_HOME"/src/command/dc.sh

cjdev::help() {
  echo -e "Cangjie's developer util script

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-V$(ansi::resetFg), $(ansi::cyan)--version$(ansi::resetFg)       Print version info and exit
  $(ansi::cyan)-v$(ansi::resetFg), $(ansi::cyan)--verbose...$(ansi::resetFg)    Use verbose output
  $(ansi::cyan)-h$(ansi::resetFg), $(ansi::cyan)--help$(ansi::resetFg)          Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)init$(ansi::resetFg), $(ansi::cyan)i$(ansi::resetFg)  Init cjdev environment
  $(ansi::cyan)build$(ansi::resetFg)    Build Cangjie's projects
  $(ansi::cyan)test$(ansi::resetFg)     Test Cangjie's projects
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
    -v | --verbose)
      verbose_level+=1
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
  log::init

  local help_requested=
  local verbose_level=0
  typeset -i verbose_level
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

    cjdev::help
    ;;
  esac
}

cjdev "$@"
