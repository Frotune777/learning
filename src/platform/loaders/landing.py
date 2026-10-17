"""Landing layer loader for raw downloads and manifest registration."""

from __future__ import annotations

from datetime import date
from pathlib import Path


class LandingLoader:
    """Manages raw immutable downloads into data/landing/."""

    def __init__(self, landing_root: Path | str = "data/landing") -> None:
        self.landing_root = Path(landing_root)

    def download(self, source: str, trade_date: date) -> str:
        """Download raw archive and register manifest. Returns batch_id."""
        raise NotImplementedError

    def validate_manifest(self, batch_id: str) -> bool:
        """Verify checksum integrity of a landing batch."""
        raise NotImplementedError
