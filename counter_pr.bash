# 今のブランチの前にあるプルリクエストブランチに対して、カウンタープルリクエストを作成する。

function hiho_counter_pr() {
  # HEADから過去5回分のコミットを探索し、カウンタープルリクエスト対象のブランチを決定
  attempts=5
  branches=""
  for ((i = 0; i < attempts; i++)); do
    commit_ref="HEAD"
    for ((j = 0; j < i; j++)); do
      commit_ref+="^"
    done

    branches=$(git branch -r --contains "$commit_ref" | sed 's/\* //g' | tr -d ' ' | grep -vE '^(origin|upstream)/' | grep -vE '^pr/.+/[0-9]+$' || true)
    if [[ -n "$branches" ]]; then
      break
    fi
  done

  if [[ -z "$branches" ]]; then
    echo "Error: 対象のブランチが見つかりません。"
    return 1
  fi

  # ブランチの候補が1つだけならそのブランチを使用
  if [[ $(echo "$branches" | wc -l) -eq 1 ]]; then
    pr_branch="$branches"
    pr_hash=$(git rev-parse "$pr_branch")
  else
    # 複数のブランチがある場合は選択
    echo "現在のコミットに関連するブランチがあります。どのブランチを使用しますか？"
    select pr_branch in $branches; do
      if [[ -n "$pr_branch" ]]; then
        break
      else
        echo "無効な選択です。もう一度選んでください。"
      fi
    done
  fi

  if [[ "$pr_branch" =~ ^([^/]+)/(.+)$ ]]; then
    pr_owner="${BASH_REMATCH[1]}"
    pr_branch="${BASH_REMATCH[2]}"
  else
    echo "Error: ブランチ名の形式が認識できません。期待される形式は pr_owner/pr_branch です。"
    return 1
  fi

  # リモートURLから自分の名前とリポジトリ名を抽出
  git_remote_url=$(git config --get remote.origin.url)
  if [[ -z "$git_remote_url" ]]; then
    echo "Error: Gitリポジトリが見つかりません。"
    return 1
  fi

  if [[ "$git_remote_url" =~ ^git@github.com:(.+)/(.+)\.git$ ]]; then
    my_owner="${BASH_REMATCH[1]}"
    my_repo="${BASH_REMATCH[2]}"
  elif [[ "$git_remote_url" =~ ^https://github.com/(.+)/(.+)\.git$ ]]; then
    my_owner="${BASH_REMATCH[1]}"
    my_repo="${BASH_REMATCH[2]}"
  else
    echo "Error: GitリポジトリのURL形式が認識できません。"
    return 1
  fi

  # プルリクエスト用の新しいブランチを作成
  my_branch="hiho-counter-pr-$(git rev-parse --short=8 HEAD)"

  if ! git show-ref --verify --quiet "refs/heads/$my_branch"; then
    git checkout -b "$my_branch"
    git push -u origin "$my_branch"
  fi

  # 変更があればコミットするか確認してコミットする
  if ! git diff --exit-code; then
    echo "変更があります。コミットしますか？ (y/n)"
    read -r user_input

    if [[ "$user_input" == "y" ]]; then
      git add .
      git commit -m "カウンタープルリクエスト用の変更"
      git push origin "$my_branch"
    fi
  fi

  # 文面を整える
  upstream_url=$(git config --get remote.upstream.url)
  if [[ "$upstream_url" =~ ^git@github.com:(.+)/(.+)\.git$ ]]; then
    upstream_owner="${BASH_REMATCH[1]}"
  elif [[ "$upstream_url" =~ ^https://github.com/(.+)/(.+)\.git$ ]]; then
    upstream_owner="${BASH_REMATCH[1]}"
  else
    echo "Error: upstreamリポジトリのURL形式が認識できません。"
    return 1
  fi

  pr_info=$(gh pr list --repo "$upstream_owner/$my_repo" --search "$pr_hash" --json title,number)
  pr_number=$(echo "$pr_info" | jq -r '.[0].number')
  pr_link="https://github.com/$upstream_owner/$my_repo/pull/$pr_number"

  pr_title="#${pr_number} の変更提案プルリクエスト"
  pr_body="- ${pr_link}

の変更提案プルリクです！

mergeしていただければ自動的に元のプルリクに反映されるはずです。
もちろんmergeせず自由に変更いただいても問題ないです！"

  # 意思の確認
  echo "作成するプルリクエストの詳細:"
  echo "リポジトリ: $pr_owner/$my_repo"
  echo "ブランチ: $pr_branch"
  echo "タイトル: $pr_title"
  echo -e "本文: \n$pr_body"
  echo ""
  echo "プルリクエストを作成してもよろしいですか？ (y/n)"
  read -r user_input

  if [[ "$user_input" != "y" ]]; then
    echo "プルリクエストの作成をキャンセルしました。"
    return 0
  fi

  # プルリクエストを作成
  set +e

  gh pr create --repo "$pr_owner/$my_repo" --head "$my_owner:$my_repo:$my_branch" --base "$pr_branch" --title "$pr_title" --body "$pr_body"
  if [[ $? -ne 0 ]]; then
    echo "Error: プルリクエストの作成に失敗しました。"
    return 1
  fi
  set -e

  echo "プルリクエストが正常に作成されました。"
}
