# TODO: use args instead of global vars

dc::help() {
  echo -e "Execute a command in the cjdev container

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 dc [OPTIONS] -- [COMMAND] [ARGS]...$(ansi::resetFg)

$(ansi::green)Arguments:$(ansi::resetFg)
  $(ansi::cyan)[ARGS]...$(ansi::resetFg)    Arguments for the command to execute

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-h$(ansi::resetFg), $(ansi::cyan)--help$(ansi::resetFg)   Print help."
  exit 1
}

dc::pwd() {
  # Cut the prefix
  # /home/filaco/Projects/cjdev/a/b/c -> /a/b/c
  local relpath="${PWD#"$CJDEV_HOST_WORKDIR"}"

  local res="$CJDEV_CONTAINER_WORKDIR"
  if [ -n "$relpath" ]; then
    res="$res$relpath"
  fi

  echo "$res"
}

dc::init() {
  docker buildx build -t cjdev "$CJDEV_SCRIPTS_HOME"
}

dc() {
  if [[ "$help_requested" == true ]]; then
    dc::help
  fi

  if [[ "$#" -gt 0 ]] && [[ "$1" == -- ]]; then
    shift
  fi

  docker container run \
    -it \
    --rm \
    -v "$CJDEV_HOST_WORKDIR":"$CJDEV_CONTAINER_WORKDIR":rw \
    -w "$(dc::pwd)" \
    cjdev \
    bash -lc "$(
      IFS=' '
      echo "$*"
    )"
}
