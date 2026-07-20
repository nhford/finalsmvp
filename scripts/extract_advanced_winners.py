"""Extract winner advanced box scores from cached series HTML → CSVs.

Basketball-Reference series pages only include advanced tables from 1984 on.
Earlier Finals (1969–1983) are skipped with a note.

Usage:
  python3 scripts/extract_advanced_winners.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.boxscores import fix_player_name_encoding

SERIES_HTML_FINALS_DIR = ROOT / "data" / "series_html" / "finals"
OUT_DIR = ROOT / "data" / "series_tables" / "advanced" / "winner"

# BBR markup is typically: <strong>League Champion</strong>: <a href='/teams/BOS/2024.html'>
CHAMP_RE = re.compile(
    r"League Champion</strong>\s*:\s*<a href=['\"]/teams/([A-Z]{3})/\d{4}\.html['\"]",
    re.I,
)
CHAMP_RE_LOOSE = re.compile(r"League Champion.*?/teams/([A-Z]{3})/\d{4}\.html", re.S | re.I)


def winner_abbrev(html: str) -> str | None:
    m = CHAMP_RE.search(html) or CHAMP_RE_LOOSE.search(html)
    return m.group(1) if m else None


def extract_table_from_div(page: BeautifulSoup, div_id: str) -> pd.DataFrame:
    container = page.find(id=div_id)
    if container is None:
        raise ValueError(f"Missing div id={div_id}")

    table = container.find("table")
    if table is None:
        for c in container.find_all(string=lambda t: isinstance(t, Comment)):
            inner = BeautifulSoup(c, "html.parser")
            table = inner.find("table")
            if table is not None:
                break
    if table is None:
        raise ValueError(f"No table inside {div_id}")

    df = pd.read_html(io.StringIO(str(table)))[0]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            c[-1] if isinstance(c, tuple) else c for c in df.columns.to_flat_index()
        ]
    if "Rk" in df.columns:
        df = df.drop(columns=["Rk"])
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wrote, skipped, failed = [], [], []

    for path in sorted(SERIES_HTML_FINALS_DIR.glob("*_nba_finals_*.html")):
        year = int(path.name.split("_")[0])
        html = path.read_text(encoding="utf-8", errors="replace")
        abbrev = winner_abbrev(html)
        if not abbrev:
            failed.append((path.name, "no winner abbrev"))
            continue

        page = BeautifulSoup(html, "html.parser")
        div_id = f"all_{abbrev}advanced"
        if page.find(id=div_id) is None:
            skipped.append((year, abbrev, "no advanced table on page"))
            continue

        try:
            df = extract_table_from_div(page, div_id)
        except Exception as exc:  # noqa: BLE001
            failed.append((path.name, str(exc)))
            continue

        if "Player" in df.columns:
            df["Player"] = df["Player"].map(
                lambda value: fix_player_name_encoding(value)
                if pd.notna(value) and str(value).lower() != "team totals"
                else value
            )

        out = OUT_DIR / path.name.replace(".html", ".csv")
        df.to_csv(out, index=False)
        wrote.append((year, abbrev, out.name, len(df)))
        print(f"wrote {out.name} ({abbrev}, {len(df)} rows)")

    print(
        f"\nDone: wrote {len(wrote)}, skipped {len(skipped)} (no advanced on BBR), "
        f"failed {len(failed)}"
    )
    if skipped:
        years = [y for y, _, _ in skipped]
        print(f"Skipped years (no advanced): {min(years)}–{max(years)} ({len(years)} series)")
    if failed:
        print("Failures:")
        for name, err in failed:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    main()
