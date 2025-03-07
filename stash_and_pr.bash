# 今のGit変更をプルリクエストにする。
# 途中でgit stashを使う。

function hiho_stash_and_pr() {
  # 必要なコマンドがあるか確認
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
    return 1
  fi

  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  # 引数処理
  if [ $# -lt 1 ]; then
    echo "Usage: $0 <commit/PR message>"
    return 1
  fi

  pr_title="$1"

  current_branch=$(git branch --show-current)

  changes=$(git status --porcelain)
  if [ -n "$changes" ]; then
    git stash push --include-untracked
  fi

  # リモート名を取得
  if git remote get-url upstream &>/dev/null; then
    remote="upstream"
  else
    remote="origin"
  fi

  # リモートのデフォルトブランチを取得
  default_branch=$(git remote show "$remote" | sed -n '/HEAD branch/s/.*: //p')
  if [ -z "$default_branch" ]; then
    if git ls-remote --heads "$remote" main &>/dev/null; then
      default_branch="main"
    else
      default_branch="master"
    fi
  fi

  # リモートの最新を取得
  git fetch "$remote"
  git checkout "$remote/$default_branch"
  git pull "$remote" "$default_branch"

  if ! git stash pop; then
    echo "Error: stash popでコンフリクトが発生しました。処理を中止します。"
    git checkout "$current_branch"
    return 1
  fi

  # 新規ブランチを作成
  branch_name="hiho-$(date +'%Y%m%d-%H%M%S')"
  git checkout -b "$branch_name"

  git add .
  git commit -m "$pr_title"

  git push -u origin "$branch_name"

  # リポジトリ情報取得
  git_remote_url=$(git config --get remote.origin.url)
  if [[ "$git_remote_url" =~ git@github.com:(.+)/(.+)\.git ]]; then
    my_owner="${BASH_REMATCH[1]}"
    my_repo="${BASH_REMATCH[2]}"
  elif [[ "$git_remote_url" =~ https://github.com/(.+)/(.+)\.git ]]; then
    my_owner="${BASH_REMATCH[1]}"
    my_repo="${BASH_REMATCH[2]}"
  else
    echo "Error: GitリポジトリURL形式が認識できません。"
    git checkout "$current_branch"
    return 1
  fi

  upstream_url=$(git config --get remote.upstream.url)
  if [[ "$upstream_url" =~ git@github.com:(.+)/(.+)\.git ]]; then
    upstream_owner="${BASH_REMATCH[1]}"
    upstream_repo="${BASH_REMATCH[2]}"
  elif [[ "$upstream_url" =~ https://github.com/(.+)/(.+)\.git ]]; then
    upstream_owner="${BASH_REMATCH[1]}"
    upstream_repo="${BASH_REMATCH[2]}"
  else
    echo "Error: upstreamリポジトリのURL形式が認識できません。"
    git checkout "$current_branch"
    return 1
  fi

  # PR本文
  pr_body="\
## 内容

$pr_title

## 関連 Issue

## スクリーンショット・動画など

## その他
"

  echo "以下の内容でプルリクエストを作成します:"
  echo "タイトル: $pr_title"
  echo -e "本文:\n$pr_body"
  echo ""
  echo "プルリクエストを作成してよろしいですか？ (y/n)"
  read -r user_input

  if [[ "$user_input" != "y" ]]; then
    echo "プルリクエストの作成をキャンセルしました。"
    git checkout "$current_branch"
    exit 0
  fi

  set +e
  gh pr create \
    --repo "$upstream_owner/$upstream_repo" \
    --base "$default_branch" \
    --head "$my_owner:$my_repo:$branch_name" \
    --title "$pr_title" \
    --body "$pr_body"

  if [[ $? -ne 0 ]]; then
    echo "Error: プルリクエストの作成に失敗しました。"
    git checkout "$current_branch"
    return 1
  fi
  set -e

  echo "プルリクエストが正常に作成されました。"

  git checkout "$current_branch"
}
