log::init() {
  local log_file="$CJDEV_LOG_DIR"/latest.log
  local log_file_desc=3
  mkdir -p "$CJDEV_LOG_DIR"
  exec "$log_file_desc" >"$log_file"
}

log::with_date() {
  echo "[$(date -Is)]" "$@"
}

log::error() {
  echo todo
}
