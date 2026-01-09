#!/bin/bash

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_dir=$(cd "$script_dir/.." && pwd)
bashrc_path="${repo_dir}/.bashrc"

sync_shell_config() {
  local config_file="$1"
  local config_name=$(basename "$config_file")

  if [[ ! -f "$config_file" ]]; then
    touch "$config_file"
    echo "作成しました: $config_file"
  fi

  if [[ ! -r "$config_file" ]] || [[ ! -w "$config_file" ]]; then
    echo "エラー: $config_file の読み書き権限がありません"
    return 1
  fi

  local marker_line="# hiho_scripts"
  local source_line="source ${bashrc_path}"

  local temp_file
  temp_file=$(mktemp) || {
    echo "エラー: 一時ファイルの作成に失敗しました"
    return 1
  }

  local found_marker=false
  local found_source=false
  local source_is_correct=false
  local marker_line_num=0
  local line_num=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line_num=$((line_num + 1))
    if [[ "$line" == "$marker_line" ]]; then
      found_marker=true
      marker_line_num=$line_num
    fi
  done < "$config_file"

  if $found_marker; then
    line_num=0
    while IFS= read -r line || [[ -n "$line" ]]; do
      line_num=$((line_num + 1))
      if [[ $line_num -eq $((marker_line_num + 1)) ]]; then
        if [[ "$line" =~ ^source[[:space:]] ]]; then
          found_source=true
          if [[ "$line" == "$source_line" ]]; then
            source_is_correct=true
          fi
        fi
        break
      fi
    done < "$config_file"
  fi

  if $found_marker && $found_source && $source_is_correct; then
    rm -f "$temp_file"
    echo "✓ $config_name は既に正しく設定されています"
    return 0
  fi

  if $found_marker && $found_source && ! $source_is_correct; then
    line_num=0
    while IFS= read -r line || [[ -n "$line" ]]; do
      line_num=$((line_num + 1))
      if [[ $line_num -eq $((marker_line_num + 1)) ]]; then
        echo "$source_line" >> "$temp_file"
      else
        echo "$line" >> "$temp_file"
      fi
    done < "$config_file"

    mv "$temp_file" "$config_file" || {
      echo "エラー: $config_file の更新に失敗しました"
      rm -f "$temp_file"
      return 1
    }
    echo "✓ $config_name の hiho_scripts パスを更新しました"
    return 0
  fi

  if $found_marker && ! $found_source; then
    line_num=0
    while IFS= read -r line || [[ -n "$line" ]]; do
      line_num=$((line_num + 1))
      echo "$line" >> "$temp_file"
      if [[ $line_num -eq $marker_line_num ]]; then
        echo "$source_line" >> "$temp_file"
      fi
    done < "$config_file"

    mv "$temp_file" "$config_file" || {
      echo "エラー: $config_file の更新に失敗しました"
      rm -f "$temp_file"
      return 1
    }
    echo "✓ $config_name に hiho_scripts の source 行を追加しました"
    return 0
  fi

  {
    echo "$marker_line"
    echo "$source_line"
    echo ""
    cat "$config_file"
  } > "$temp_file"

  mv "$temp_file" "$config_file" || {
    echo "エラー: $config_file の更新に失敗しました"
    rm -f "$temp_file"
    return 1
  }
  echo "✓ $config_name に hiho_scripts の source 行を追加しました"
  return 0
}

main() {
  echo "hiho_scripts を bashrc/zshrc に同期します..."
  echo ""

  sync_shell_config "$HOME/.bashrc"
  local bashrc_result=$?

  sync_shell_config "$HOME/.zshrc"
  local zshrc_result=$?

  echo ""
  if [[ $bashrc_result -eq 0 ]] && [[ $zshrc_result -eq 0 ]]; then
    echo "完了しました"
    return 0
  else
    echo "一部のファイルで失敗しました"
    return 1
  fi
}

main
