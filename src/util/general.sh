str::ascii_upper() {
  echo "$1" | tr '[:lower:]' '[:upper:]'
}

str::ascii_lower() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}
