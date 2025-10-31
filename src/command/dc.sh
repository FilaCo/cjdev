# TODO: use args instead of global vars

dc::help() {
  echo -e "Execute a command in the cjdev container

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 dc [OPTIONS] -- [COMMAND] [ARGS]...$(ansi::resetFg)

$(ansi::green)Arguments:$(ansi::resetFg)
  $(ansi::cyan)[ARGS]...$(ansi::resetFg)    Arguments for the command to execute

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-h, --help$(ansi::resetFg)   Print help"
  exit 1
}

dc::pwd() {
  # Cut the prefix
  # /home/filaco/Projects/cjdev/a/b/c -> /a/b/c
  local relpath="${PWD#"$HOST_WORKDIR"}"

  local res="$CONTAINER_WORKDIR"
  if [ -n "$relpath" ]; then
    res="$res$relpath"
  fi

  echo "$res"
}

dc::setup() {
  docker buildx build -t cjdev "$HOST_WORKDIR"
}

dc() {
  docker container run \
    -it \
    --rm \
    -v "$HOST_WORKDIR":"$CONTAINER_WORKDIR":rw \
    -w "$(dc::pwd)" \
    cjdev \
    "$@"
}
