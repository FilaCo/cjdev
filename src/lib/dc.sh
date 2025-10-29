# TODO: use args instead of global vars

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
