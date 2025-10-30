git-mm::help() {
  echo -e "Git multirepo management util script

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)git mm [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-V, --version$(ansi::resetFg)  Print version info and exit
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)sync$(ansi::resetFg)       Sync all repos with upstreams
  $(ansi::cyan)start$(ansi::resetFg)      Start a new branch
  $(ansi::cyan)upload, u$(ansi::resetFg)  Upload branches to upstreams

See '$(ansi::cyan)git mm help <command>$(ansi::resetFg)' for more information on a specific command."
  exit 1
}

git-mm::version() {
  echo "git mm $VERSION"
  exit 0
}

git-mm::sync() {
  echo -e "git mm sync"
}

git-mm::start() {
  echo -e "git mm start"
}

git-mm() {
  local p
  [ ! p = "$(
    getopt \
      -o hV \
      -l help,version \
      -n 'git mm' -- "$@"
  )" ]

  eval set -- "$p"
  while true; do
    case "$1" in
    -V | --version)
      git-mm::version
      ;;
    -h | --help)
      git-mm::help
      ;;
    --)
      shift
      break
      ;;
    esac
  done
}
