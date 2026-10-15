#!/usr/bin/env python3
"""
combine_py.py — bundle every relevant source file of a Python project into ONE text file.

Why: so the whole project can be pasted / attached in a single shot and fully
understood in one go (by a human or an LLM).

What it does
------------
* Walks the project tree and collects source files (default: *.py, *.pyi).
* Skips the usual junk: .git, .venv, venv, __pycache__, build, dist, node_modules,
  .idea, .vscode, caches, binaries, lock files, images, notebooks artefacts, ...
* Writes a single file containing:
    - a header (root, timestamp, stats)
    - an ASCII directory tree of the included files
    - each file's content, clearly delimited and labelled with its relative path

Usage
-----
    python combine_py.py
    python combine_py.py -r /path/to/project -o bundle.txt
    python combine_py.py --ext .py .pyi .toml --include requirements.txt README.md
    python combine_py.py --line-numbers
    python combine_py.py --exclude-dir tests migrations --no-tree

Only the standard library is used.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# Defaults — what to ignore
# --------------------------------------------------------------------------- #

DEFAULT_EXCLUDE_DIRS = {
    # version control
    ".git", ".hg", ".svn", ".bzr",
    # virtual environments / installed packages
    ".venv", "venv", "env", "virtualenv", ".virtualenv", "site-packages",
    # caches
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".cache", ".nox", "htmlcov", ".hypothesis",
    # build artefacts
    "build", "dist", ".eggs",
    # editors / IDEs
    ".idea", ".vscode", ".vs", ".settings",
    # JS deps (for mixed projects)
    "node_modules", "bower_components",
    # infra
    ".terraform", ".serverless",
}

DEFAULT_EXCLUDE_GLOBS = [
    # compiled / binary python
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib",
    # packaging metadata
    "*.egg-info", "*.whl", "*.tar.gz", "*.zip",
    # minified / generated
    "*.min.js", "*.min.css", "*.map",
    # data / models / logs
    "*.log", "*.sqlite", "*.sqlite3", "*.db", "*.pkl", "*.pickle",
    "*.joblib", "*.h5", "*.pt", "*.pth", "*.onnx", "*.npy", "*.npz", "*.parquet",
    # media / docs
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.svg", "*.ico",
    "*.pdf", "*.docx", "*.xlsx", "*.pptx", "*.mp4", "*.mov",
    # lock files (huge, no value for review)
    "package-lock.json", "poetry.lock", "Pipfile.lock", "yarn.lock", "uv.lock",
    # OS noise
    ".DS_Store", "Thumbs.db", "desktop.ini",
]

DEFAULT_EXTENSIONS = [".py", ".pyi"]

SEPARATOR = "# " + "=" * 77


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="combine_py",
        description="Bundle all relevant source files of a Python project into one file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python combine_py.py\n"
            "  python combine_py.py -r ./my_project -o my_bundle.txt\n"
            "  python combine_py.py --ext .py .pyi .toml --include requirements.txt README.md\n"
            "  python combine_py.py --exclude-dir tests --exclude 'test_*.py'\n"
        ),
    )
    parser.add_argument("root", nargs="?", default=".",
                        help="project root directory (default: current directory)")
    parser.add_argument("-o", "--output", default="project_bundle.txt",
                        help="output file (default: project_bundle.txt)")
    parser.add_argument("-e", "--ext", nargs="+", default=DEFAULT_EXTENSIONS,
                        metavar="EXT", help="file extensions to include (default: .py .pyi)")
    parser.add_argument("-i", "--include", nargs="+", default=[], metavar="GLOB",
                        help="extra file names/globs to include, e.g. requirements.txt '*.toml'")
    parser.add_argument("--exclude", nargs="+", default=[], metavar="GLOB",
                        help="file globs to skip, e.g. 'test_*.py'")
    parser.add_argument("--exclude-dir", nargs="+", default=[], metavar="DIR",
                        help="additional directory names to skip, e.g. tests migrations")
    parser.add_argument("--no-default-excludes", action="store_true",
                        help="do not apply the built-in ignore lists")
    parser.add_argument("--max-size", type=int, default=1_000_000, metavar="BYTES",
                        help="skip files larger than this (default: 1000000)")
    parser.add_argument("--no-tree", dest="tree", action="store_false",
                        help="do not print the directory tree")
    parser.add_argument("--line-numbers", action="store_true",
                        help="prefix every source line with its line number")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="only print the final summary")
    return parser


# --------------------------------------------------------------------------- #
# File collection
# --------------------------------------------------------------------------- #

def collect_files(root: Path, extensions: set[str], include_globs: list[str],
                  exclude_dirs: set[str], exclude_globs: list[str],
                  output_path: Path, max_size: int):
    """Return (kept_files, skipped_files)."""
    kept: list[Path] = []
    skipped: list[tuple[Path, str]] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune directories in-place so os.walk never descends into them.
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in exclude_dirs
            and not d.startswith(".")          # .git, .venv, .idea, ...
            and not d.endswith(".egg-info")
        )

        for name in sorted(filenames):
            path = Path(dirpath) / name

            # Never include the bundle we are writing.
            try:
                if path.resolve() == output_path:
                    continue
            except OSError:
                pass

            if any(fnmatch.fnmatch(name, g) for g in exclude_globs):
                continue

            suffix = path.suffix.lower()
            wanted = suffix in extensions or any(
                fnmatch.fnmatch(name, g) for g in include_globs
            )
            if not wanted:
                continue

            try:
                size = path.stat().st_size
            except OSError as exc:
                skipped.append((path, f"unreadable ({exc})"))
                continue

            if size > max_size:
                skipped.append((path, f"too large ({size} bytes)"))
                continue

            kept.append(path)

    kept.sort(key=lambda p: p.relative_to(root).as_posix().lower())
    return kept, skipped


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #

def build_tree(paths: list[Path], root: Path) -> str:
    """Render an ASCII tree of the given relative paths."""
    tree: dict = {}
    for path in paths:
        node = tree
        for part in path.relative_to(root).parts:
            node = node.setdefault(part, {})

    lines: list[str] = []

    def render(node: dict, prefix: str = "") -> None:
        items = sorted(node.items(), key=lambda kv: (not bool(kv[1]), kv[0].lower()))
        for index, (name, child) in enumerate(items):
            last = index == len(items) - 1
            lines.append(prefix + ("└── " if last else "├── ") + name)
            if child:
                render(child, prefix + ("    " if last else "│   "))

    render(tree)
    return "\n".join(lines)


def read_text(path: Path) -> str:
    """Read a text file, tolerating encoding problems."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"<could not read file: {exc}>\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def number_lines(text: str) -> str:
    lines = text.splitlines()
    width = len(str(len(lines)))
    return "".join(f"{i:>{width}} | {line}\n" for i, line in enumerate(lines, 1))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"error: '{root}' is not a directory", file=sys.stderr)
        return 2

    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = (Path.cwd() / output_path).resolve()
    else:
        output_path = output_path.resolve()

    extensions = {
        e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.ext
    }

    exclude_dirs = set(args.exclude_dir)
    exclude_globs = list(args.exclude)
    if not args.no_default_excludes:
        exclude_dirs |= DEFAULT_EXCLUDE_DIRS
        exclude_globs += DEFAULT_EXCLUDE_GLOBS

    files, skipped = collect_files(
        root=root,
        extensions=extensions,
        include_globs=args.include,
        exclude_dirs=exclude_dirs,
        exclude_globs=exclude_globs,
        output_path=output_path,
        max_size=args.max_size,
    )

    if not files:
        print("error: no matching source files found.", file=sys.stderr)
        return 1

    # ---- gather content first so we can report accurate stats ------------- #
    sections: list[tuple[str, int, str]] = []
    total_lines = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = read_text(path)
        line_count = len(text.splitlines())
        total_lines += line_count
        body = number_lines(text) if args.line_numbers else text
        sections.append((rel, line_count, body))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(SEPARATOR + "\n")
        fh.write(f"# PROJECT BUNDLE: {root.name}\n")
        fh.write(f"# Root       : {root}\n")
        fh.write(f"# Generated  : {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"# Files      : {len(sections)}\n")
        fh.write(f"# Total lines: {total_lines}\n")
        fh.write(SEPARATOR + "\n\n")

        if args.tree:
            fh.write("## DIRECTORY TREE\n\n")
            fh.write(build_tree(files, root) + "\n\n")
            fh.write(SEPARATOR + "\n\n")

        for rel, line_count, body in sections:
            fh.write(SEPARATOR + "\n")
            fh.write(f"# FILE: {rel}  ({line_count} lines)\n")
            fh.write(SEPARATOR + "\n")
            fh.write(body)
            if not body.endswith("\n\n"):
                fh.write("\n")
            fh.write("\n")

        fh.write(SEPARATOR + "\n")
        fh.write("# END OF BUNDLE\n")
        fh.write(SEPARATOR + "\n")

    # ---- report ----------------------------------------------------------- #
    if not args.quiet:
        for rel, line_count, _ in sections:
            print(f"  + {rel}  ({line_count} lines)")
        if skipped:
            print("\n  skipped:")
            for path, reason in skipped:
                print(f"  - {path.relative_to(root).as_posix()}  ({reason})")

    size_kb = output_path.stat().st_size / 1024
    print(
        f"\nBundled {len(sections)} file(s), {total_lines} lines "
        f"-> {output_path}  ({size_kb:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())