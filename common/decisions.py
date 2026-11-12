"""Append human Accept / Override decisions to a CSV log."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def save_decision(record: dict, path: Path, columns: list[str]) -> None:
    row = pd.DataFrame([{c: record.get(c, "") for c in columns}])
    row.to_csv(path, mode="a", header=not path.exists(), index=False)


def load_decisions(path: Path, columns: list[str]) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")
