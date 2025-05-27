# bashスクリプトを一時ファイルに移動してから実行する。
# スクリプトが存在するパスが変わるので注意。

function hiho_bash_run() {
  local script_path="$1"
  if [[ ! -f "$script_path" ]]; then
    echo "エラー: スクリプトファイルが存在しません: $script_path"
    return 1
  fi

  local temp_script
  temp_script=$(mktemp /tmp/hiho_bash_run.XXXXXX)
  cp "$script_path" "$temp_script"
  bash "$temp_script"
  rm -f "$temp_script"
}
