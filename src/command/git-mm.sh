git-mm::help::all() {
  echo -e "Git multirepo management util commands

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)sync$(ansi::resetFg)       Sync all repos with upstreams
  $(ansi::cyan)start$(ansi::resetFg)      Start a new branch
  $(ansi::cyan)upload, u$(ansi::resetFg)  Upload branches to upstreams

See '$(ansi::cyan)$0 git-mm help <command>$(ansi::resetFg)' for more information on a specific command."
  exit 1

}

git-mm::help() {
  [ "$#" -eq 0 ] && git-mm::help::all

  local cmd="$1"
  shift
  case "$cmd" in
  start)
    git-mm::start::help "$@"
    ;;
  sync)
    git-mm::sync::help "$@"
    ;;
  u | upload)
    git-mm::upload::help "$@"
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`git-mm $cmd\`" >&2
    git-mm::help
    ;;
  esac
}

git-mm::getopt() {
  [ "$#" -eq 0 ] && set -- help
  local p
  if ! p=$(getopt -o h -l help -n "$0" -- "$@"); then
    git-mm::help
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
    local opt="$1"
    shift
    if [ "$cmd" = help ]; then
      cmd_opts+=("--$opt")
      break
    fi
    cmd_opts+=("$opt")
  done
}

git-mm() {
  local cmd=
  local cmd_opts=()

  git-mm::getopt "$@"

  case "$cmd" in
  help)
    git-mm::help "${cmd_opts[@]}"
    ;;
  sync)
    git-mm::sync "${cmd_opts[@]}"
    ;;
  start)
    git-mm::start "${cmd_opts[@]}"
    ;;
  u | upload)
    git-mm::upload "${cmd_opts[@]}"
    ;;
  *)
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: \`$cmd\`" >&2
    git-mm::help
    ;;
  esac
}
