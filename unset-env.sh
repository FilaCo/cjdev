#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

source ./src/aliases.sh

for alias in "${ALIASES[@]}"; do
  unalias "$alias" 2>/dev/null || true
done

unset "$ALIASES"
