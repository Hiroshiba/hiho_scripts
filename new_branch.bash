# 新しいブランチを作成して、そのブランチに切り替える。

function new_branch() {
  prefix="${1:-hiho}"

  branch_name="${prefix}-$(date +'%Y%m%d-%H%M%S')"
  git checkout -b "$branch_name"

  echo "Switched to new branch '$branch_name'"
}
