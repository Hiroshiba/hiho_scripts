#!/bin/bash

# shellcheck disable=SC1091

script_dir=$(
  cd $(dirname ${BASH_SOURCE:-$0})
  pwd
)

source "${script_dir}/get_contributors.bash"

unset script_dir
