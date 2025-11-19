git-mm::help() {
  echo -e "Git multirepo management util commands

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm [OPTIONS] [COMMAND]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-h$(ansi::resetFg), $(ansi::cyan)--help$(ansi::resetFg)     Print help

$(ansi::green)Commands:$(ansi::resetFg)
  $(ansi::cyan)init$(ansi::resetFg), $(ansi::cyan)i$(ansi::resetFg)    Init git-mm environment
  $(ansi::cyan)sync$(ansi::resetFg)       Sync all repos with upstreams
  $(ansi::cyan)start$(ansi::resetFg)      Start a new branch
  $(ansi::cyan)upload$(ansi::resetFg), $(ansi::cyan)u$(ansi::resetFg)  Creates pull requests to upstreams with commited changes."

  exit 1
}

git-mm::init::help() {
  echo -e "Init git-mm environment

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm init [OPTIONS]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-b$(ansi::resetFg), $(ansi::cyan)--branch$(ansi::resetFg)   A remote branch for tracking updates, defaults to dev
  $(ansi::cyan)-h$(ansi::resetFg), $(ansi::cyan)--help$(ansi::resetFg)     Print help."

  exit 1
}

git-mm::sync::help() {
  echo -e "Sync all repos with upstreams

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm sync [OPTIONS]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)--sync-fork$(ansi::resetFg)    Sync gitcode fork
  $(ansi::cyan)-h$(ansi::resetFg), $(ansi::cyan)--help$(ansi::resetFg)     Print help."

  exit 1
}

git-mm::start::help() {
  echo -e "Starts a new branch

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm start [OPTIONS] <branch>$(ansi::resetFg)

$(ansi::green)Arguments:$(ansi::resetFg)
  $(ansi::cyan)<branch>$(ansi::resetFg)   A branch to checkout

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-h, --help$(ansi::resetFg)   Print help."

  exit 1
}

git-mm::upload::help() {
  echo -e "Creates pull requests to upstreams with commited changes

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 git-mm upload [OPTIONS]$(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-T, --title$(ansi::resetFg)    A title for the pull request
  $(ansi::cyan)-h, --help$(ansi::resetFg)     Print help."

  exit 1
}

git-mm::init::getopt() {
  local p
  if ! p=$(getopt -o b: -l branch: -n "$0" -- "$@"); then
    git-mm::init::help
  fi

  eval set -- "$p"
  unset p
  while [[ "$#" -gt 0 ]]; do
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

  if [[ -z "$branch" ]]; then
    branch=dev
  fi
}

# TODO: to utils
# $1 - config full key, e.g. module.cangjie_compiler.origin
git-mm::config::get() {
  git config get -f "$CJDEV_GIT_MM_CONFIG_FILE" "$1"
}

#TODO: to utils
# $1 - config full key, e.g. module.cangjie_compiler.branch
# $2 - value
git-mm::config::set() {
  git config set -f "$CJDEV_GIT_MM_CONFIG_FILE" "$1" "$2"
}

# TODO: to utils
# $1 - config key
git-mm::config::iter() {
  git config -f "$CJDEV_GIT_MM_CONFIG_FILE" --list | grep "$1"= | sed "s/.*$1\s*=\s*//" | tr -d ' '
}

git-mm::init::impl() {
  for path in $(git-mm::config::iter path); do
    if [[ ! -e "$path" ]]; then
      git clone --branch "$1" "$(git-mm::config::get module."$path".origin)" "$path"
    fi

    git-mm::config::set module."$path".branch "$1"

    cd "$path"
    git remote set-url origin "$(git-mm::config::get module."path".origin)"
    if ! git remote | grep -q "^upstream$"; then
      git remote add upstream "$(git-mm::config::get module."$path".upstream)"
    fi
    cd - >/dev/null
  done

  git-mm::start "$1"
}

git-mm::init() {
  if [[ "$help_requested" == true ]]; then
    git-mm::init::help
  fi
  local branch=
  git-mm::init::getopt "$@"
  git-mm::init::impl "$branch"
}

git-mm::sync() {
  if [[ "$help_requested" == true ]]; then
    git-mm::sync::help
  fi

  for path in $(git-mm::config::iter path); do
    cd "$CJDEV_HOST_WORKDIR"/"$path"

    local base_branch=
    base_branch="$(git-mm::config::get module."$path".branch)"
    git fetch --quiet upstream
    git switch "$base_branch"
    git rebase --quiet upstream/"$base_branch"
    git push -f origin "$base_branch"

    git switch - >/dev/null
    git rebase "$base_branch"

    cd - >/dev/null
  done
}

git-mm::start::getopt() {
  local p
  if ! p=$(getopt -o '' -n "$0" -- "$@"); then
    git-mm::start::help
  fi

  eval set -- "$p"
  unset p
  while [[ "$#" -gt 0 ]]; do
    local opt="$1"
    shift
    case "$opt" in
    --)
      break
      ;;
    esac
  done

  if [[ "$#" -eq 0 ]]; then
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): <branch> argument was not found" >&2
    git-mm::start::help
  fi

  branch="$1"
  shift
}

git-mm::start() {
  if [[ "$help_requested" == true ]]; then
    git-mm::start::help
  fi

  local branch=
  git-mm::start::getopt "$@"
  for path in $(git-mm::config::iter path); do
    cd "$CJDEV_HOST_WORKDIR"/"$path"
    git switch -c "$branch" 2>/dev/null || git switch "$branch"
    cd - >/dev/null
  done
}

git-mm::upload::getopt() {
  local p
  if ! p=$(getopt -o T -l title -n "$0" -- "$@"); then
    git-mm::upload::help
  fi

  eval set -- "$p"
  unset p
  while [[ "$#" -gt 0 ]]; do
    local opt="$1"
    shift
    case "$opt" in
    --)
      break
      ;;
    -T | --title)
      title="$1"
      shift
      ;;
    esac
  done

  if [[ -z "$title" ]]; then
    #TODO:: to error report utils
    echo -e "$(ansi::red)error$(ansi::resetFg): required \`--title\` option was not found" >&2
    git-mm::upload::help

  fi
}

git-mm::upload() {
  if [[ "$help_requested" == true ]]; then
    git-mm::upload::help
  fi

  local title=
  git-mm::upload::getopt "$@"
  echo todo
}

# pos0 pos1 ... posN opt0 opt1 ... optN
git-mm() {
  # No args or no subcommand
  if [[ "$#" -eq 0 ]] || [[ "$1" == -- ]]; then
    if [[ "$help_requested" != true ]]; then
      #TODO:: to error report utils
      echo -e "$(ansi::red)error$(ansi::resetFg): no command provided for git-mm" >&2
    fi
    git-mm::help
  fi

  local cmd="$1"
  shift
  local cmd_opts=("$@")

  case "$cmd" in
  i | init)
    git-mm::init "${cmd_opts[@]}"
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
    echo -e "$(ansi::red)error$(ansi::resetFg): no such command: git-mm \`$cmd\`" >&2
    git-mm::help
    ;;
  esac
}
