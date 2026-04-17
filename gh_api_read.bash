#!/bin/bash

# gh api の読み取り専用ラッパー。書き込み系フラグとgraphqlエンドポイントをブロックする

function hiho_gh_api_read() {
  if ! command -v gh >/dev/null; then
    echo "エラー: ghコマンドが見つかりません。ghコマンドをインストールしてください。" >&2
    return 1
  fi

  if [ $# -lt 1 ]; then
    echo "使い方: hiho_gh_api_read <endpoint> [gh api オプション...]" >&2
    echo "  書き込み系フラグ (-f, -F, --field, --raw-field, --input) と graphql エンドポイントはブロックされます。" >&2
    return 1
  fi

  local endpoint="$1"

  if [ "$endpoint" = "graphql" ]; then
    echo "エラー: graphql エンドポイントは mutation の可能性があるため使用できません。生の gh api コマンドを使用してください。" >&2
    return 1
  fi

  local args=("$@")
  local i=1

  while [ $i -lt ${#args[@]} ]; do
    local arg="${args[$i]}"

    case "$arg" in
      -f|--raw-field|-F|--field)
        echo "エラー: ${arg} フラグは書き込み操作になるため使用できません。" >&2
        return 1
        ;;
      -f=*|--raw-field=*|-F=*|--field=*)
        echo "エラー: ${arg%%=*} フラグは書き込み操作になるため使用できません。" >&2
        return 1
        ;;
      --input)
        echo "エラー: --input フラグはリクエストボディを指定するため使用できません。" >&2
        return 1
        ;;
      --input=*)
        echo "エラー: --input フラグはリクエストボディを指定するため使用できません。" >&2
        return 1
        ;;
      -X|--method)
        local next_i=$((i + 1))
        if [ $next_i -ge ${#args[@]} ]; then
          echo "エラー: ${arg} に HTTP メソッドが指定されていません。" >&2
          return 1
        fi
        local method="${args[$next_i]}"
        if [ "${method^^}" != "GET" ]; then
          echo "エラー: HTTP メソッド ${method} は使用できません。GET のみ許可されています。" >&2
          return 1
        fi
        i=$((next_i + 1))
        continue
        ;;
      --method=*)
        local method="${arg#--method=}"
        if [ "${method^^}" != "GET" ]; then
          echo "エラー: HTTP メソッド ${method} は使用できません。GET のみ許可されています。" >&2
          return 1
        fi
        ;;
    esac

    i=$((i + 1))
  done

  set +e
  gh api "$@"
  local exit_code=$?
  set -e

  return $exit_code
}
