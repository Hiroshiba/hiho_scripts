#!/bin/bash

# shellcheck disable=SC1091

script_dir=$(
  cd "$(dirname ${BASH_SOURCE:-$0})" || exit
  pwd
)

source "${script_dir}/get_contributors.bash"
source "${script_dir}/show_diff_with_default_branch.bash"
source "${script_dir}/stash_and_pr.bash"

unset script_dir
