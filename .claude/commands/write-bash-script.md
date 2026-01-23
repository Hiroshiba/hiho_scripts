---
name: write-bash-script
description: bash スクリプトの作成・修正
---

## タスク

```
$ARGUMENTS
```

## 準備

以下の既存ファイルを読んでパターンを把握すること:

- get_contributors.bash
- get_pr_detail_comments_review_threads.bash
- pbcopy_files.bash
- new_branch.bash
- stash_and_pr.bash

## 規約

### ファイル構成

- 配置: 直下
- 拡張子: `.bash`
- 1ファイル1関数

### フォーマット

```bash
# 関数の説明（日本語、1-2行）

function hiho_関数名() {
  # 1. 依存コマンド確認
  # 2. 引数処理 + バリデーション
  # 3. ローカル変数初期化
  # 4. メイン処理
}
```

### コーディング規則

- 関数名: `hiho_` プレフィックス + スネークケース
- ローカル変数: 必ず `local` を付ける、スネークケース小文字
- エラー出力: 日本語で `>&2` に出力
- 戻り値: エラー時 `return 1`、正常時 `return 0` または `return`
- 依存コマンド確認: `if ! command -v xxx >/dev/null; then`
- 一時ファイル使用時: `trap` でクリーンアップ

## .bashrc への追記

新規作成時は `.bashrc` に source 行を追加すること。
既存ファイルと同じ形式で追加: `source "${script_dir}/ファイル名.bash"`
