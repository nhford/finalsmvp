"""Scrape Finals game box scores → win/loss eFG% + PTS_CV + closeout PTS CSVs.

Uses the same game HTML cache as Q4 extraction under
data/series_html/boxscores/ (gitignored). Analysis reads the committed CSVs:

  data/meta/finals_wl_efg_by_game.csv
  data/meta/finals_wl_efg_by_series.csv
  data/meta/finals_pts_cv_by_series.csv
  data/meta/finals_closeout_pts_by_series.csv

Usage:
  python3 scripts/extract_wl_efg.py
  python3 scripts/extract_wl_efg.py --min-year 2020
  python3 scripts/extract_wl_efg.py --year 2018
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

from helpers.closeout import aggregate_series_closeout_pts  # noqa: E402
from helpers.paths import (  # noqa: E402
    BASE_URL,
    FINALS_CLOSEOUT_PTS_BY_SERIES_CSV,
    FINALS_PTS_CV_BY_SERIES_CSV,
    FINALS_WL_EFG_BY_GAME_CSV,
    FINALS_WL_EFG_BY_SERIES_CSV,
    META_DIR,
    SERIES_HTML_BOXSCORES_DIR,
    SERIES_HTML_FINALS_DIR,
)
from helpers.pts_cv import aggregate_series_pts_cv  # noqa: E402
from helpers.q4 import (  # noqa: E402
    date_from_game_id,
    game_links_from_series_html,
    parse_box_game_id,
    series_stem_from_path,
)
from helpers.wl_efg import aggregate_series_wl_efg, parse_game_wl  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; finalsmvp-research/1.0; +https://github.com/)",
}

WL_MIN_YEAR = 1969


def fetch(url: str, sleep: float, retries: int = 5) -> str:
    print(f"GET {url}", flush=True)
    last_err: Exception | None = None
    for attempt in range(retries):
        time.sleep(sleep if attempt == 0 else max(sleep, 15.0) * (attempt + 1))
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code == 429:
            last_err = requests.HTTPError(
                f"429 Too Many Requests for {url}", response=r
            )
            print(f"  rate-limited; retry {attempt + 1}/{retries}", flush=True)
            continue
        r.raise_for_status()
        return r.content.decode("utf-8", errors="replace")
    assert last_err is not None
    raise last_err


def load_or_fetch_game(
    game_id: str,
    sleep: float,
    cache_only: bool = False,
) -> str | None:
    cache_dir = Path(SERIES_HTML_BOXSCORES_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{game_id}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    if cache_only:
        return None
    html = fetch(f"{BASE_URL}/boxscores/{game_id}.html", sleep=sleep)
    path.write_text(html, encoding="utf-8")
    print(f"  cached {path}")
    return html


def process_series(
    series_path: Path,
    sleep: float,
    min_year: int,
    cache_only: bool = False,
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
        game_html = load_or_fetch_game(game_id, sleep=sleep, cache_only=cache_only)
        if game_html is None:
            print(f"  {stem} G{game_num} ({game_id}): not in cache; skip")
            continue
        box = parse_game_wl(game_html)
        if box.empty:
            print(f"  {stem} G{game_num} ({game_id}): no game-basic tables")
            continue
        box.insert(0, "Year", year)
        box.insert(1, "Series", stem)
        box.insert(2, "Game", game_num)
        box.insert(3, "Date", date_from_game_id(game_id))
        box.insert(4, "BoxScore", game_id)
        rows.append(box)
        print(f"  {stem} G{game_num}: {len(box)} player-rows")

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-year",
        type=int,
        default=WL_MIN_YEAR,
        help=f"First Finals year to scrape (default {WL_MIN_YEAR})",
    )
    parser.add_argument("--sleep", type=float, default=3.0, help="Seconds between GETs")
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        default=None,
        help="Only process this calendar year (repeatable)",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Never hit the network; skip games missing from the local HTML cache",
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
        frame = process_series(
            path,
            sleep=args.sleep,
            min_year=args.min_year,
            cache_only=args.cache_only,
        )
        if not frame.empty:
            frames.append(frame)

    Path(META_DIR).mkdir(parents=True, exist_ok=True)
    if not frames:
        print("No win/loss eFG rows extracted.")
        return

    by_game = pd.concat(frames, ignore_index=True)
    cols = [
        "Year",
        "Series",
        "Game",
        "Date",
        "BoxScore",
        "Team",
        "Won",
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
        "eFG%",
    ]
    by_game = by_game[[c for c in cols if c in by_game.columns]]

    # Partial runs (--year) merge into any existing game log instead of wiping it.
    game_path = Path(FINALS_WL_EFG_BY_GAME_CSV)
    if args.year and game_path.exists():
        prior = pd.read_csv(game_path)
        prior = prior[~prior["Year"].isin(args.year)]
        by_game = pd.concat([prior, by_game], ignore_index=True)
        by_game = by_game.sort_values(
            ["Year", "Series", "Game", "Team", "Player"],
            ascending=[False, True, True, True, True],
        ).reset_index(drop=True)

    by_game.to_csv(FINALS_WL_EFG_BY_GAME_CSV, index=False)

    by_series = aggregate_series_wl_efg(by_game)
    by_series.to_csv(FINALS_WL_EFG_BY_SERIES_CSV, index=False)

    pts_cv = aggregate_series_pts_cv(by_game)
    pts_cv.to_csv(FINALS_PTS_CV_BY_SERIES_CSV, index=False)

    closeout = aggregate_series_closeout_pts(by_game)
    closeout.to_csv(FINALS_CLOSEOUT_PTS_BY_SERIES_CSV, index=False)

    print(
        f"\nWrote {FINALS_WL_EFG_BY_GAME_CSV} "
        f"({len(by_game)} rows, {by_game.BoxScore.nunique()} games, "
        f"{by_game.Year.min()}–{by_game.Year.max()})"
    )
    print(
        f"Wrote {FINALS_WL_EFG_BY_SERIES_CSV} "
        f"({len(by_series)} player-series rows)"
    )
    print(
        f"Wrote {FINALS_PTS_CV_BY_SERIES_CSV} "
        f"({len(pts_cv)} player-series rows)"
    )
    print(
        f"Wrote {FINALS_CLOSEOUT_PTS_BY_SERIES_CSV} "
        f"({len(closeout)} player-series rows)"
    )


if __name__ == "__main__":
    main()
