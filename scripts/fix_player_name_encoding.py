"""Repair mojibake in Player columns under data/series_tables/."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.boxscores import fix_player_name_encoding

TABLES_DIR = ROOT / "data" / "series_tables"


def main() -> None:
    repaired = 0
    files = 0
    for path in sorted(TABLES_DIR.rglob("*.csv")):
        df = pd.read_csv(path)
        if "Player" not in df.columns:
            continue
        before = df["Player"].astype(str)
        after = before.map(
            lambda value: value
            if value.lower() in {"nan", "team totals"}
            else fix_player_name_encoding(value)
        )
        changed = (before != after).sum()
        if changed:
            df["Player"] = after
            df.to_csv(path, index=False)
            files += 1
            repaired += int(changed)
            print(f"{path.relative_to(ROOT)}: {changed} name(s)")
    print(f"\nRepaired {repaired} player name(s) across {files} file(s)")


if __name__ == "__main__":
    main()
