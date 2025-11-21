declare -A group_dirs
declare -A group_configs

test::util::initialize_maps() {
  local hlt_name='hlt'
  local hlt_dir="$CJDEV_HOST_WORKDIR"/cangjie_test/testsuites/HLT
  local hlt_config="$hlt_dir"/configs/cjnative/cangjie2cjnative_linux_x86_test.cfg
  group_dirs["$hlt_name"]="$hlt_dir"
  group_configs["$hlt_name"]="$hlt_config"

  local llt_name='llt'
  local llt_dir="$CJDEV_HOST_WORKDIR"/cangjie_test/testsuites/LLT
  local llt_config="$llt_dir"/configs/cjnative/cjnative_test.cfg
  group_dirs["$llt_name"]="$llt_dir"
  group_configs["$llt_name"]="$llt_config"

  local cjpm_name='cjpm'
  local cjpm_dir="$CJDEV_HOST_WORKDIR"/cangjie_test/testsuites/LLT/Tools/cjpm
  local cjpm_config="$cjpm_dir"/test.cfg
  group_dirs["$cjpm_name"]="$cjpm_dir"
  group_configs["$cjpm_name"]="$cjpm_config"
}

test::help() {
  echo -e "Test Cangjie's projects

$(ansi::green)Usage:$(ansi::resetFg) $(ansi::cyan)$0 test [OPTIONS] -- [ARGS] $(ansi::resetFg)

$(ansi::green)Options:$(ansi::resetFg)
  $(ansi::cyan)-f$(ansi::resetFg), $(ansi::cyan)--file$(ansi::resetFg)         Specify testlist file to read from
  $(ansi::cyan)-g [GROUPS]$(ansi::resetFg),
  $(ansi::cyan)--groups [GROUPS]$(ansi::resetFg)  Specify testcase group to run (known: ${!group_dirs[@]})
  $(ansi::cyan)-d$(ansi::resetFg), $(ansi::cyan)--dump-fail$(ansi::resetFg)    Create testlist, which stores failed testcases"

  exit 1
}

# Note: the groups looks like so
# --------- default file: $CJDEV_HOST_WORKDIR/test_cases ---------
# [ CJPM ]
# Path/to/cjpm/llt/test/file.info
# # Commented/out/cases/are/ignored.info
#
# [ LLT ] 
# Path/to/llt/test/file.info
#
# ![ CJPM ] # banged groups are ignored
# This/group/will/be/ignored.info
# --------------------------------------------------
# `cjdev test -g cjpm` will run particular group 


# Usage: 
# $ test::util::read_group <source> <dest> <group>
test::util::read_group() {
    local source="$1"
    local dest="$2"
    local group="$(str::ascii_upper "$3")"
    echo "$source" | awk \
        -v group="$group" \
        'BEGIN { printing=0; }
         (/\[ .* \]/ && printing) { printing=0; }
         (toupper($0) ~ "\\[ " group " \\]" && !/^!/ && !printing) { printing=1; next }
         (!(/\[ .* \]/) && printing) { print $0 }
        ' >> "$dest"
}

# Usage: 
# $ test::util::dump_group <source> <dest> <group>
test::util::dump_group() {
    local source="$1"
    local dest="$2"
    local group="$(str::ascii_upper "$3")"

    local sedness=$(echo "$source" | sed -n 's/.*Case: \(.*\), Result: FAIL,.*/\1/p')
    echo "[ $group ]
$sedness
" >> "$dest"
}

# Usage: 
# $ test::util::run_group <source> <group> <test_dir> <config_file>
test::util::run_group() {
  local source="$1"
  local group_name="$(str::ascii_upper "$2")"
  local test_dir="$3"
  local config_file="$4"

  local testlist_tmp=$(mktemp "$tmpdir/runtest.XXXXXX")
  test::util::read_group "$source" "$testlist_tmp" "$group_name"
  if [ ! -s $testlist_tmp ]; then
      echo -e "$(ansi::yellow)warning$(ansi::resetFg): no \`[ $group_name ]\` test files were specified. Skipping..." >&2
  else 
      # FD shenanigans to keep test progress visible
      exec 3>&1
      local test_output=$( (python3 "$CJDEV_HOST_WORKDIR"/cangjie_test_framework/main.py \
          --test_cfg="$config_file" "$test_dir" \
          --test_list=$testlist_tmp --fail-verbose -pFAIL -j10 --debug \
          --temp_dir=$CJDEV_SCRIPTS_HOME/test_temp/ \
          "${main_py_opts[@]}"
          ) 2>&1 1>&3 | tee /dev/stderr)
      exec 3>&-

      # TODO: Would be good if failed testcases were dumped even after SIGINT
      if $dump_fail; then
          test::util::dump_group "$test_output" "$dumpfile" "$group_name"
      fi
  fi
}

test() {
  test::util::initialize_maps

  if [[ "$help_requested" == true ]]; then
    test::help
  fi

  local test_list=$CJDEV_HOST_WORKDIR/test_cases
  local dump_fail=false
  local groups_to_run=()
  local -n main_py_opts=cmd_args
  test::getopt "$@"

  if [ ${#groups_to_run[@]} -eq 0 ]; then
    echo -e "$(ansi::red)error$(ansi::resetFg): need to specify at least one test group to run" >&2;
    test::help
  fi

  echo -e "$(ansi::blue)info$(ansi::resetFg): selected groups: ${groups_to_run[@]}" >&2;

  if [ ! ${#main_py_opts[@]} -eq 0 ]; then
    echo -e "$(ansi::blue)info$(ansi::resetFg): additional options for \`cangjie_test_framework/main.py\`: ${main_py_opts[@]}" >&2;
  fi

  if [ ! -f $test_list ]; then
      echo -e "$(ansi::red)error$(ansi::resetFg): file '$test_list' not found!" >&2
      exit 1
  fi

  tmpdir=$(mktemp -d /tmp/runtest-dir.XXXXXX)

  # Note: comment this trap if deemed necessary
  trap '{
      rm -rf -- "$tmpdir";
      echo -e "$(ansi::blue)info$(ansi::resetFg): deleted test directory: $tmpdir" >&2;
  }' EXIT INT
  
  echo -e "$(ansi::blue)info$(ansi::resetFg): new test directory: $tmpdir" >&2
  
  # Remove commented out testcases and blank lines (`#`) and blocks (!)
  local input=$(
      sed -n -e '/^#.*/!p' $test_list | 
      sed -E 's/[[:blank:]]+/ /g' |
      sed '$a\' | sed 's/^ *//g' | 
      grep . )
  
  dumpfile=/dev/null
  if $dump_fail; then
      dumpfile=$(mktemp "$CJDEV_HOST_WORKDIR/dumped_cases.XXXXXX")
      echo -e "$(ansi::blue)info$(ansi::resetFg): created dump file $dumpfile" >&2
  fi 

  # Check if key exists
  for group in "${groups_to_run[@]}"; do
    if [[ -n "${group_configs[$group]+x}" ]] && [[ -n "${group_dirs[$group]+x}" ]]; then
      local group_dir="${group_dirs[$group]}"
      local group_config="${group_configs[$group]}"
      echo -e "$(ansi::blue)info$(ansi::resetFg): running test group: \`$group\`" >&2
      test::util::run_group "$input" "$group" "$group_dir" "$group_config"
    else
      echo -e "$(ansi::yellow)warning$(ansi::resetFg): unknown test group: \`$group\`" >&2
    fi
  done

  if $dump_fail; then
      echo -e "$(ansi::blue)info$(ansi::resetFg): failed testcases were dumped in: $dumpfile" >&2
  fi
}

test::getopt() {
  local collecting_groups=false
  local -A requested_groups=()
  while [[ "$#" -gt 0 ]]; do
    local opt="$1"
    shift
    case "$opt" in
      -g | --groups)
        collecting_groups=true
        ;;
      --* | -*)
        collecting_groups=false
        ;;& # continue after match
      -f | --file ) 
        test_list="$1"
        shift
        ;;
      -d | --dump-fail)
        dump_fail=true
        ;;
      *)
        if [ $collecting_groups = false ]; then
          echo -e "$(ansi::red)error$(ansi::resetFg): no such option: \`$opt\`" >&2
          test::help
        else
            local group="$(str::ascii_lower "$opt")"
            if [ -z "${requested_groups[$group]+x}"]; then
                groups_to_run+=("$group")
                requested_groups+=("$group")
            fi
          while [[ $# -gt 0 && "$1" != -* && "$1" != "--" ]]; do
            local group="$(str::ascii_lower "$1")"
            if [ -z "${requested_groups[$group]+x}"]; then
                groups_to_run+=("$group")
                requested_groups+=("$group")
            fi
            shift
          done
        fi
        ;;
    esac
  done

}

