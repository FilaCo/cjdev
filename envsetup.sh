# absolute path of a workspace directory on host machine
HOST_WORKDIR=/home/filaco/Projects/cjdev
# absolute path of a workspace directory in a container
CONTAINER_WORKDIR=/home/cjdev/Projects
VERSION="$(<"$HOST_WORKDIR"/VERSION)"

source "$HOST_WORKDIR/src/lib/dc.sh"

# Setup aliases to commands that desired to be executed in the docker container
source "$HOST_WORKDIR/aliases.sh"
for alias in "${ALIASES[@]}"; do
  alias "$alias=dc $alias"
done

source "$HOST_WORKDIR/src/lib/git-mm.sh"
