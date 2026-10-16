import pytest
from src.cli.formatters import ok, warn, err, tip


def test_ok_returns_string():
    res = ok("Operation successful")
    assert isinstance(res, str)
    assert "Operation successful" in res
    assert "✔" in res


def test_warn_returns_string():
    res = warn("Caution advised")
    assert isinstance(res, str)
    assert "Caution advised" in res
    assert "!" in res


def test_err_returns_string():
    res = err("Fatal error")
    assert isinstance(res, str)
    assert "Fatal error" in res
    assert "✘" in res


def test_tip_returns_string():
    res = tip("Pro tip here")
    assert isinstance(res, str)
    assert "Pro tip here" in res
    assert "→" in res


def test_cli_actions_interpolation_no_none():
    scanned_count = 100
    msg = f"{ok('SMC Scan Finished')}: Scanned {scanned_count} securities."
    assert "None:" not in msg
    assert "SMC Scan Finished" in msg
    assert "Scanned 100 securities." in msg
