# git remote のうち origin と upstream 以外を削除する

function hiho_git_remote_clean() {
  # 必要なコマンドがあるか確認
  if ! command -v git >/dev/null; then
    echo "エラー: gitコマンドが見つかりません。gitコマンドをインストールしてください。" >&2
    return 1
  fi

  # リモート名を取得
  local remotes
  remotes=$(git remote)
  for remote in $remotes; do
    if [ "$remote" != "origin" ] && [ "$remote" != "upstream" ]; then
      echo "リモート $remote を削除します..."
      git remote remove "$remote"
    fi
  done
}
