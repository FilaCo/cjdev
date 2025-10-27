HOST_WORKDIR=/home/filaco/Projects/cjdev

source "$HOST_WORKDIR"/src/aliases.sh

for alias in "${ALIASES[@]}"; do
  unalias "$alias" 2>/dev/null || true
done
