cjdev::git-mm::help::all() {
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

cjdev::git-mm::help() {
  echo "implement"
}

cjdev::git-mm() {
  echo "implement cjdev::git-mm"
}
