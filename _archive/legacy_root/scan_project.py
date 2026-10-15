"""
File: scan_project.py
Purpose: One-shot project reconnaissance for the SMC Signal Engine build.
Outputs a single file: project_audit.txt
"""

from __future__ import annotations

import ast
import os
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
OUTPUT = ROOT / "project_audit.txt"

# Folders to ignore entirely
IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", "node_modules", "dist", "build", ".idea", ".vscode",
    "merge this", ".ipynb_checkpoints", "site-packages", ".egg-info",
    "htmlcov", ".coverage", ".tox",
    # IDE / CLI caches that sometimes hold temp files
    ".antigravitycli", ".cursor", ".windsurf", ".continue", ".aider",
    ".cache", ".local", ".config", ".npm", ".cursor-server",
}

# Files to ignore when listing
IGNORE_FILE_SUFFIXES = {".pyc", ".pyo", ".log", ".prof", ".lock", ".tmp"}

# Key files we want to dump the full content of
KEY_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    ".env copy.example",
    ".env.example",
    "main.py",
]

# Directories we want to inspect for structure
KEY_DIRS = ["src", "data", "config", "scripts"]


def write(lines: list[str], fp) -> None:
    for line in lines:
        fp.write(line + "\n")


def banner(text: str) -> str:
    return f"\n{'=' * 80}\n{text}\n{'=' * 80}\n"


def safe_stat(entry: Path) -> int | None:
    """Return file size or None if the file vanished / is a broken symlink."""
    try:
        return entry.stat().st_size
    except (FileNotFoundError, OSError, PermissionError):
        return None


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def walk_tree(root: Path, prefix: str = "", depth: int = 0, max_depth: int = 4) -> list[str]:
    """Recursively build a tree view, skipping ignored dirs and broken links."""
    lines: list[str] = []
    if depth > max_depth:
        return lines

    try:
        raw_entries = list(root.iterdir())
    except (PermissionError, FileNotFoundError, OSError):
        return [f"{prefix}[Permission Denied / Missing]"]

    # Filter out ignored dirs, broken symlinks, and ignored suffixes
    entries: list[Path] = []
    for e in raw_entries:
        if e.name in IGNORE_DIRS:
            continue
        # Skip broken symlinks
        try:
            if e.is_symlink() and not e.exists():
                continue
        except OSError:
            continue
        if e.is_file() and e.suffix in IGNORE_FILE_SUFFIXES:
            continue
        entries.append(e)

    entries.sort(key=lambda x: (x.is_file(), x.name.lower()))

    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        try:
            is_dir = entry.is_dir()
        except OSError:
            continue

        if is_dir:
            lines.append(f"{prefix}{connector}{entry.name}/")
            extension = "    " if is_last else "│   "
            lines.extend(walk_tree(entry, prefix + extension, depth + 1, max_depth))
        else:
            size = safe_stat(entry)
            if size is None:
                lines.append(f"{prefix}{connector}{entry.name}  [unavailable]")
            else:
                lines.append(f"{prefix}{connector}{entry.name}  ({format_size(size)})")

    return lines


def extract_module_summary(path: Path) -> dict:
    """Extract docstrings, classes, and function signatures from a Python file."""
    info = {"file": str(path.relative_to(ROOT)), "docstring": None, "classes": [], "functions": []}
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception as e:
        info["error"] = str(e)
        return info

    info["docstring"] = ast.get_docstring(tree)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            info["classes"].append({"name": node.name, "methods": methods})
        elif isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            info["functions"].append({"name": node.name, "args": args})

    return info


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except Exception:
        return -1


def list_data_files(data_dir: Path) -> list[str]:
    """Summarize the data/ folder."""
    lines: list[str] = []
    if not data_dir.exists():
        return ["[data/ directory does not exist]"]

    for sub in sorted(data_dir.rglob("*")):
        try:
            if sub.is_dir():
                continue
            rel = sub.relative_to(ROOT)
            size = safe_stat(sub)
            if size is None:
                continue
            lines.append(f"  {rel}  ({format_size(size)})")
        except Exception:
            continue

    if len(lines) > 500:
        lines = lines[:500] + [f"  ... ({len(lines) - 500} more files truncated)"]
    return lines


def read_safe(path: Path, max_bytes: int = 200_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if len(text) > max_bytes:
            return text[:max_bytes] + f"\n\n[TRUNCATED at {max_bytes} bytes]"
        return text
    except Exception as e:
        return f"[Unable to read: {e}]"


def main() -> None:
    with OUTPUT.open("w", encoding="utf-8") as fp:
        write([f"PROJECT AUDIT — generated {datetime.now().isoformat()}"], fp)
        write([f"Project Root: {ROOT}"], fp)

        # 1. Project tree
        write([banner("1. PROJECT TREE (max depth 4, ignoring junk)")], fp)
        write(walk_tree(ROOT), fp)

        # 2. Key config files
        write([banner("2. KEY CONFIG FILES")], fp)
        for kf in KEY_FILES:
            p = ROOT / kf
            if p.exists():
                write([f"\n--- {kf} ---\n"], fp)
                write([read_safe(p)], fp)

        # 3. Python module inventory
        write([banner("3. PYTHON MODULE INVENTORY (classes, functions, docstrings)")], fp)
        py_files: list[Path] = []
        for d in KEY_DIRS + ["."]:
            base = ROOT / d
            if not base.exists():
                continue
            for p in base.rglob("*.py"):
                if any(ig in p.parts for ig in IGNORE_DIRS):
                    continue
                py_files.append(p)

        py_files = sorted(set(py_files))
        write([f"\nTotal Python files (excl. junk): {len(py_files)}\n"], fp)

        for p in py_files:
            try:
                rel = p.relative_to(ROOT)
            except ValueError:
                continue
            loc = count_lines(p)
            summary = extract_module_summary(p)
            write([f"\n### {rel}  ({loc} lines)"], fp)
            if summary.get("docstring"):
                ds = summary["docstring"].strip().split("\n")[0]
                write([f"  Doc: {ds}"], fp)
            for cls in summary.get("classes", []):
                write([f"  class {cls['name']}  (methods: {', '.join(cls['methods']) or 'none'})"], fp)
            for fn in summary.get("functions", []):
                write([f"  def {fn['name']}({', '.join(fn['args'])})"], fp)

        # 4. Data directory inventory
        write([banner("4. DATA DIRECTORY INVENTORY")], fp)
        write(list_data_files(ROOT / "data"), fp)

        # 5. .env keys (values redacted)
        write([banner("5. ENVIRONMENT VARIABLE KEYS (values redacted)")], fp)
        for env_name in [".env", ".env copy.example", ".env.example"]:
            env_path = ROOT / env_name
            if not env_path.exists():
                continue
            write([f"\n--- {env_name} ---"], fp)
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        write([line], fp)
                        continue
                    if "=" in line:
                        key = line.split("=", 1)[0]
                        write([f"{key}=<REDACTED>"], fp)
            except Exception as e:
                write([f"[Error: {e}]"], fp)

        # 6. Git info
        write([banner("6. GIT STATUS")], fp)
        if (ROOT / ".git").exists():
            os.system(f'git -C "{ROOT}" status --short >> "{OUTPUT}" 2>&1')
            os.system(f'git -C "{ROOT}" branch --show-current >> "{OUTPUT}" 2>&1')
            os.system(f'git -C "{ROOT}" log -5 --oneline >> "{OUTPUT}" 2>&1')
        else:
            write(["[Not a git repository]"], fp)

        # 7. Installed dependencies
        write([banner("7. INSTALLED DEPENDENCIES (uv pip list)")], fp)
        os.system(f'uv pip list >> "{OUTPUT}" 2>&1')

        write([banner("END OF AUDIT")], fp)

    print(f"\n✅ Audit written to: {OUTPUT}")
    print(f"   Size: {OUTPUT.stat().st_size / 1024:.1f} KB")
    print(f"\n📤 Please paste the contents of project_audit.txt into the chat.")


if __name__ == "__main__":
    main()