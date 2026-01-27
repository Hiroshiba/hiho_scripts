import subprocess
from pathlib import Path


def get_repo_root() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise Exception("リポジトリのルートを取得できませんでした")
    return result.stdout.strip()


def get_worktree_path(branch_name: str) -> Path:
    repo_root = get_repo_root()
    worktrees_dir = Path(f"{repo_root}.worktrees")
    return worktrees_dir / branch_name


def worktree_exists(worktree_path: Path) -> bool:
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
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), branch_name],
        capture_output=True,
    )
    return result.returncode == 0


def setup_claude_symlink(worktree_path: Path) -> None:
    repo_root = get_repo_root()
    claude_dir = Path(repo_root) / ".claude"
    worktree_claude = worktree_path / ".claude"

    if claude_dir.exists() and not worktree_claude.exists():
        worktree_claude.symlink_to(claude_dir)
