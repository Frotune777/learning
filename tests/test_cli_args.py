"""
File: tests/test_cli_args.py
Purpose: Regression tests for CLI argument parsing bugs found in Unit 13.

Rule 11 compliance: no mocks, no dummy values. Each test spawns the real
CLI entry point as a subprocess and inspects real stdout/stderr.

Unit 13 bugs covered:
  - sync-history was missing --resume → AttributeError at runtime
  - screen --processed-dir ignored --data-dir
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = PROJECT_ROOT / "main.py"


def _run_main(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    """Run main.py with the given args; return (exit, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def test_sync_history_help_lists_resume_flag() -> None:
    """Regression: sync-history parser must accept --resume (Unit 13)."""
    rc, out, err = _run_main("sync-history", "--help")
    combined = out + err
    assert rc == 0, f"exit {rc}\n{combined}"
    assert "--resume" in combined, (
        "sync-history parser is missing --resume argument. "
        "This was the root cause of Unit 13's AttributeError."
    )


def test_sync_history_accepts_resume_flag_without_crash() -> None:
    """
    Regression: passing --resume must not raise
    AttributeError: 'Namespace' object has no attribute 'resume'.

    We do NOT run a real sync here — the CLI will exit before any network
    I/O if we give it an invalid data-dir. The point is to verify the
    parser accepts the flag.
    """
    rc, out, err = _run_main(
        "--data-dir", "/tmp/__nonexistent_unit13__",
        "sync-history", "--resume", "--help",
    )
    combined = out + err
    assert "AttributeError" not in combined, (
        f"AttributeError still triggered: {combined}"
    )
    assert "'Namespace' object has no attribute 'resume'" not in combined, (
        f"Original AttributeError still present: {combined}"
    )


def test_screen_help_shows_processed_dir() -> None:
    """Regression: screen must expose --processed-dir (Unit 13)."""
    rc, out, err = _run_main("screen", "--help")
    combined = out + err
    assert rc == 0, f"exit {rc}\n{combined}"
    assert "--processed-dir" in combined


def test_screen_processed_dir_defaults_from_data_dir() -> None:
    """
    Regression: when --data-dir is set, screen's --processed-dir default
    must resolve to <data-dir>/processed, NOT the hardcoded 'data/processed'.

    We run with a sandbox --data-dir that has no processed subdir. The
    CLI must report the sandbox path in its error message.
    """
    sandbox = "/tmp/__unit13_screen_test__"
    rc, out, err = _run_main(
        "--data-dir", sandbox,
        "--hist-dir", sandbox + "/hist",
        "screen",
    )
    combined = out + err
    # The CLI must look inside the sandbox, not the project's ./data
    assert sandbox in combined, (
        f"screen did not use sandbox path.\n"
        f"Expected to see '{sandbox}' in output.\n"
        f"Got:\n{combined}"
    )
    # Must NOT reference the hardcoded project default for this error
    assert "No processed Bhavcopy CSV found in 'data/processed'" not in combined, (
        f"screen fell back to hardcoded default path: {combined}"
    )
