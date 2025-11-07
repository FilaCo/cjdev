build::help() {
  echo "implement cjdev::build::help"
}

build::cjc() {
  cd cangjie_compiler
  dc python3 build.py build -t debug --no-tests --build-cjdb && python3 build.py install
  rsync -a output "$CJDEV_HOST_WORKDIR/dist"
  cd - >/dev/null
}

build() {
  build::cjc
}
