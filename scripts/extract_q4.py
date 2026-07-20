"""Scrape Finals game box scores → Q4 FG/FGA CSVs.

Basketball-Reference quarterly player boxes start with the 1996-97 season
(Finals from 1997). Game HTML is cached under data/series_html/boxscores/
(gitignored). Analysis reads the committed CSVs:

  data/meta/finals_q4_by_game.csv
  data/meta/finals_q4_by_series.csv

Usage:
  python3 scripts/extract_q4.py
  python3 scripts/extract_q4.py --min-year 2020
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.paths import (  # noqa: E402
    BASE_URL,
    FINALS_Q4_BY_GAME_CSV,
    FINALS_Q4_BY_SERIES_CSV,
    META_DIR,
    SERIES_HTML_BOXSCORES_DIR,
    SERIES_HTML_FINALS_DIR,
)
from helpers.q4 import (  # noqa: E402
    Q4_MIN_YEAR,
    aggregate_series_q4,
    date_from_game_id,
    game_links_from_series_html,
    parse_box_game_id,
    parse_game_q4,
    series_stem_from_path,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; finalsmvp-research/1.0; +https://github.com/)",
}


def fetch(url: str, sleep: float) -> str:
    print(f"GET {url}")
    time.sleep(sleep)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.content.decode("utf-8", errors="replace")


def load_or_fetch_game(game_id: str, sleep: float) -> str:
    cache_dir = Path(SERIES_HTML_BOXSCORES_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{game_id}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    html = fetch(f"{BASE_URL}/boxscores/{game_id}.html", sleep=sleep)
    path.write_text(html, encoding="utf-8")
    print(f"  cached {path}")
    return html


def process_series(
    series_path: Path,
    sleep: float,
    min_year: int,
) -> pd.DataFrame:
    year = int(series_path.name.split("_")[0])
    stem = series_stem_from_path(series_path)
    if year < min_year:
        return pd.DataFrame()

    html = series_path.read_text(encoding="utf-8")
    links = game_links_from_series_html(html)
    if not links:
        print(f"  skip {stem}: no game links")
        return pd.DataFrame()

    rows: list[pd.DataFrame] = []
    for game_num, href in enumerate(links, start=1):
        game_id = parse_box_game_id(href)
        if game_id is None:
            print(f"  skip bad href {href}")
            continue
        game_html = load_or_fetch_game(game_id, sleep=sleep)
        q4 = parse_game_q4(game_html)
        if q4.empty:
            print(f"  {stem} G{game_num} ({game_id}): no Q4 tables")
            continue
        q4.insert(0, "Year", year)
        q4.insert(1, "Series", stem)
        q4.insert(2, "Game", game_num)
        q4.insert(3, "Date", date_from_game_id(game_id))
        q4.insert(4, "BoxScore", game_id)
        rows.append(q4)
        print(f"  {stem} G{game_num}: {len(q4)} player-rows")

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-year",
        type=int,
        default=Q4_MIN_YEAR,
        help=f"First Finals year to scrape (default {Q4_MIN_YEAR})",
    )
    parser.add_argument("--sleep", type=float, default=3.0, help="Seconds between GETs")
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        default=None,
        help="Only process this calendar year (repeatable)",
    )
    args = parser.parse_args()

    finals_dir = Path(SERIES_HTML_FINALS_DIR)
    if not finals_dir.exists():
        raise SystemExit(f"Missing series HTML cache: {finals_dir}")

    paths = sorted(finals_dir.glob("*_nba_finals_*.html"))
    if args.year:
        years = set(args.year)
        paths = [p for p in paths if int(p.name.split("_")[0]) in years]

    frames: list[pd.DataFrame] = []
    for path in paths:
        year = int(path.name.split("_")[0])
        if year < args.min_year:
            continue
        print(f"\n=== {path.name} ===")
        frame = process_series(path, sleep=args.sleep, min_year=args.min_year)
        if not frame.empty:
            frames.append(frame)

    Path(META_DIR).mkdir(parents=True, exist_ok=True)
    if not frames:
        print("No Q4 rows extracted.")
        return

    by_game = pd.concat(frames, ignore_index=True)
    # Stable column order
    cols = [
        "Year",
        "Series",
        "Game",
        "Date",
        "BoxScore",
        "Team",
        "Player",
        "MP",
        "FG",
        "FGA",
        "FG%",
        "3P",
        "3PA",
        "FT",
        "FTA",
        "PTS",
    ]
    by_game = by_game[[c for c in cols if c in by_game.columns]]

    # Partial runs (--year) merge into any existing game log instead of wiping it.
    game_path = Path(FINALS_Q4_BY_GAME_CSV)
    if args.year and game_path.exists():
        prior = pd.read_csv(game_path)
        prior = prior[~prior["Year"].isin(args.year)]
        by_game = pd.concat([prior, by_game], ignore_index=True)
        by_game = by_game.sort_values(
            ["Year", "Series", "Game", "Team", "Player"],
            ascending=[False, True, True, True, True],
        ).reset_index(drop=True)

    by_game.to_csv(FINALS_Q4_BY_GAME_CSV, index=False)

    by_series = aggregate_series_q4(by_game)
    by_series.to_csv(FINALS_Q4_BY_SERIES_CSV, index=False)

    print(
        f"\nWrote {FINALS_Q4_BY_GAME_CSV} "
        f"({len(by_game)} rows, {by_game.BoxScore.nunique()} games, "
        f"{by_game.Year.min()}–{by_game.Year.max()})"
    )
    print(
        f"Wrote {FINALS_Q4_BY_SERIES_CSV} "
        f"({len(by_series)} player-series rows)"
    )


if __name__ == "__main__":
    main()
