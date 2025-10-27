#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

HOST_WORKDIR=/home/filaco/Projects/cjdev
CONTAINER_WORKDIR=/home/cjdev

docker buildx build -t cjdev "$HOST_WORKDIR"

dc_pwd() {
  # Cut the prefix
  # /home/filaco/Projects/cjdev/a/b/c -> /a/b/c
  local relpath="${PWD#"$HOST_WORKDIR"}"

  local res="$CONTAINER_WORKDIR"
  if [ -n "$relpath" ]; then
    res="$res$relpath"
  fi

  echo "$res"
}

dc() {
  docker container run --rm -v "$HOST_WORKDIR":"$CONTAINER_WORKDIR":rw -w "$(dc_pwd)" cjdev "$@"
}

source ./src/aliases.sh

for alias in "${ALIASES[@]}"; do
  alias "$alias=dc $alias"
done
