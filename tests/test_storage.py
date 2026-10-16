from pathlib import Path
from src.data.storage import DataRepository


def test_data_repository_default_path():
    repo = DataRepository("1d")
    assert repo.base_path.name == "1d"
    assert repo.base_path.parent == Path("data/historical")
    assert "user_data/stock_data" not in str(repo.base_path)


def test_data_repository_explicit_base_path(tmp_path: Path):
    custom = tmp_path / "custom_dir"
    repo = DataRepository("1d", base_path=custom)
    assert repo.base_path == custom
