init::help() {
  echo -e "Initialize cjdev environment

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 init [OPTIONS]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-b, --branch$(ansi::resetFg)   A remote branch for tracking updates
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help."
  exit 1
}

init::getopt() {
  local p
  if ! p=$(getopt -o b: -l branch: -n "$0" init -- "$@"); then
    init::help
  fi

  eval set -- "$p"
  unset p
  while [ "$#" -gt 0 ]; do
    local opt="$1"
    shift
    case "$opt" in
    --)
      break
      ;;
    -b | --branch)
      branch="$1"
      shift
      ;;
    esac
  done
}

init() {
  if [ "$help_requested" == true ]; then
    init::help
  fi

  local branch=

  init::getopt "$@"
  dc::init
  git-mm::init "$branch"
}
