"""Refresh scraped Finals data, team meta CSVs, and top-8 feature tables.

HTML is written only as a local cache under data/series_html/finals,
data/series_html/meta, and data/teams/html (gitignored). Analysis reads CSVs.

Usage:
  python3 scripts/refresh_data.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(script: str) -> None:
    path = ROOT / "scripts" / script
    print(f"\n=== {script} ===")
    subprocess.check_call([sys.executable, str(path)], cwd=ROOT)


def main() -> None:
    run("update_finals_through_2026.py")
    run("parse_team_meta.py")
    # Game boxes cached under data/series_html/boxscores/ (shared by Q4 + W/L eFG).
    run("extract_q4.py")
    run("extract_wl_efg.py")
    # Top-8 after Q4 / W/L extracts so relative eFG features are present.
    run("build_top8.py")
    print("\nData refresh complete.")


if __name__ == "__main__":
    main()
