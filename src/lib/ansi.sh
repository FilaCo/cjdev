ANSI_ESC=$'\033'
ANSI_CSI="${ANSI_ESC}["
ANSI_OSC="${ANSI_ESC}]"
ANSI_ST="${ANSI_ESC}\\"

ansi::green() {
  printf '%s32m' "$ANSI_CSI"
}

ansi::blue() {
  printf '%s34m' "$ANSI_CSI"
}

ansi::cyan() {
  printf '%s36m' "$ANSI_CSI"
}

ansi::resetFg() {
  printf '%s39m' "$ANSI_CSI"
}
