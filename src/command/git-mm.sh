git-mm::help() {
  echo -e "Git multirepo management util commands

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)init, i$(ansi::resetFg)    Init git-mm environment
  $(ansi::cyan)sync$(ansi::resetFg)       Sync all repos with upstreams
  $(ansi::cyan)start$(ansi::resetFg)      Start a new branch
  $(ansi::cyan)upload, u$(ansi::resetFg)  Upload branches to upstreams."

  exit 1
}

git-mm::init() {
  echo todo
}

git-mm::sync() {
  echo "todo"
}

git-mm::start() {
  echo "todo"
}

git-mm::upload() {
  echo "todo"
}

# pos0 pos1 ... posN -- opt0 opt1 ... optN
git-mm() {
  # No args or no subcommand
  if [ "$#" -eq 0 ] || [ "$1" == -- ]; then
    if [ "$help_requested" != true ]; then
      #TODO:: to error report utils
      echo -e "$(ansi::red)error$(ansi::resetFg): no command provided for git-mm" >&2
    fi
    git-mm::help
  fi

  local cmd="$1"
  shift
  local cmd_opts=("$@")

  case "$cmd" in
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
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: git-mm \`$cmd\`" >&2
    git-mm::help
    ;;
  esac
}
