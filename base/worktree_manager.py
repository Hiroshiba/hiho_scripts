"""Git worktree 操作のユーティリティ関数を提供する"""

import subprocess
from pathlib import Path


def get_repo_root() -> str:
    """git リポジトリのルートパスを取得する"""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception("リポジトリのルートを取得できませんでした")
    return result.stdout.strip()


def get_worktree_path(branch_name: str) -> Path:
    """ブランチ名から worktree のパスを生成する"""
    repo_root = get_repo_root()
    worktrees_dir = Path(f"{repo_root}.worktrees")
    return worktrees_dir / branch_name


def worktree_exists(worktree_path: Path) -> bool:
    """指定したパスの worktree が存在するかどうかを確認する"""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
            if Path(path).resolve() == worktree_path.resolve():
                return True
    return False


def create_worktree(worktree_path: Path, branch_name: str) -> bool:
    """既存のブランチで worktree を作成する"""
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), branch_name],
        capture_output=True,
    )
    return result.returncode == 0


def create_new_branch_worktree(
    worktree_path: Path, branch_name: str, base_branch: str | None
) -> bool:
    """新しいブランチで worktree を作成する"""
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if base_branch is None:
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
            capture_output=True,
        )
    else:
        result = subprocess.run(
            [
                "git",
                "worktree",
                "add",
                str(worktree_path),
                "-b",
                branch_name,
                base_branch,
            ],
            capture_output=True,
        )
    return result.returncode == 0


def branch_exists(branch_name: str) -> bool:
    """指定したブランチが存在するかどうかを確認する"""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True,
    )
    return result.returncode == 0


def copy_local_configs(worktree_path: Path) -> None:
    """ローカル設定ファイルを worktree にコピーする"""
    import shutil

    repo_root = get_repo_root()
    repo_root_path = Path(repo_root)

    source_claude_local_md = repo_root_path / "CLAUDE.local.md"
    dest_claude_local_md = worktree_path / "CLAUDE.local.md"
    if source_claude_local_md.exists():
        shutil.copy2(source_claude_local_md, dest_claude_local_md)

    source_settings = repo_root_path / ".claude" / "settings.local.json"
    if source_settings.exists():
        dest_claude_dir = worktree_path / ".claude"
        dest_claude_dir.mkdir(parents=True, exist_ok=True)
        dest_settings = dest_claude_dir / "settings.local.json"
        shutil.copy2(source_settings, dest_settings)
