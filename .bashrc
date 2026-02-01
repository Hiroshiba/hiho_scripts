#!/bin/bash

# shellcheck disable=SC1091
# shellcheck disable=SC2139

script_dir=$(
  cd "$(dirname ${BASH_SOURCE:-$0})" || exit
  pwd
)

source "${script_dir}/bash_run.bash"
source "${script_dir}/counter_pr.bash"
source "${script_dir}/get_contributors.bash"
source "${script_dir}/get_pr_detail_comments_review_threads.bash"
source "${script_dir}/get_pr_review_thread_by_comment_id.bash"
source "${script_dir}/git_remote_clean.bash"
source "${script_dir}/new_branch.bash"
source "${script_dir}/pbcopy_files.bash"
source "${script_dir}/show_diff_with_default_branch.bash"
source "${script_dir}/stash_and_pr.bash"

alias hiho_ai_code="${script_dir}/ai_code.py"
alias hiho_ai_code_counter_pr="${script_dir}/ai_code_counter_pr.py"
alias hiho_ai_code_pr_continue="${script_dir}/ai_code_pr_continue.py"
alias hiho_get_github_template="${script_dir}/get_github_template.py"

unset script_dir
