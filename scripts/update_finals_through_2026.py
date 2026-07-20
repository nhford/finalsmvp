"""Scrape 2025–2026 NBA Finals data into the data/ layout.

Prefer ``python3 scripts/refresh_data.py`` from the repo root — that also
rebuilds team meta CSVs and ``output/full_top_8*.csv``.

HTML is written under ``data/series_html`` / ``data/teams/html`` as a local
cache only (gitignored). Analysis reads the CSV outputs.
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = "https://www.basketball-reference.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; finalsmvp-research/1.0; +https://github.com/)",
}

SERIES = [
    {
        "year": 2025,
        "slug": "2025-nba-finals-pacers-vs-thunder",
        "winner_abbrev": "OKC",
        "loser_abbrev": "IND",
        "winner_name": "Oklahoma City Thunder",
        "mvp": "Shai Gilgeous-Alexander",
    },
    {
        "year": 2026,
        "slug": "2026-nba-finals-knicks-vs-spurs",
        "winner_abbrev": "NYK",
        "loser_abbrev": "SAS",
        "winner_name": "New York Knicks",
        "mvp": "Jalen Brunson",
    },
]

SERIES_HTML_DIR = Path("data/series_html")
SERIES_HTML_FINALS_DIR = SERIES_HTML_DIR / "finals"
SERIES_HTML_META_DIR = SERIES_HTML_DIR / "meta"
TABLE_ROOT = Path("data/series_tables")
META_DIR = Path("data/meta")
TEAMS_HTML_DIR = Path("data/teams/html")


def fetch(url: str, sleep: float = 3.0) -> str:
    print(f"GET {url}")
    time.sleep(sleep)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    # Force UTF-8 so names like Jokić survive CSV export
    return r.content.decode("utf-8", errors="replace")


def series_filename(slug: str) -> str:
    from helpers.naming import finals_html_name

    return finals_html_name(slug)


def extract_table_from_div(page: BeautifulSoup, div_id: str) -> pd.DataFrame:
    """Pull a box-score table from all_{ABBREV}[advanced] (often HTML-comment wrapped)."""
    container = page.find(id=div_id)
    if container is None:
        raise ValueError(f"Missing div id={div_id}")

    table = container.find("table")
    if table is None:
        comments = container.find_all(string=lambda t: isinstance(t, Comment))
        for c in comments:
            inner = BeautifulSoup(c, "html.parser")
            table = inner.find("table")
            if table is not None:
                break
    if table is None:
        raise ValueError(f"No table inside {div_id}")

    dfs = pd.read_html(io.StringIO(str(table)))
    if not dfs:
        raise ValueError(f"pd.read_html found nothing for {div_id}")
    df = dfs[0]
    # Flatten multi-index columns when present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            c[-1] if isinstance(c, tuple) else c for c in df.columns.to_flat_index()
        ]
    return df


def save_series_tables(series: dict, html: str) -> None:
    from helpers.naming import finals_csv_name

    page = BeautifulSoup(html, "html.parser")
    slug_csv = finals_csv_name(series["slug"])
    mapping = [
        ("basic", "winner", f"all_{series['winner_abbrev']}"),
        ("basic", "loser", f"all_{series['loser_abbrev']}"),
        ("advanced", "winner", f"all_{series['winner_abbrev']}advanced"),
        ("advanced", "loser", f"all_{series['loser_abbrev']}advanced"),
    ]
    for kind, side, div_id in mapping:
        out = TABLE_ROOT / kind / side / slug_csv
        df = extract_table_from_div(page, div_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out)
        print(f"  wrote {out} ({df.shape[0]} rows)")


def refresh_finals_mvp() -> None:
    url = f"{BASE}/awards/finals_mvp.html"
    html = fetch(url)
    SERIES_HTML_META_DIR.mkdir(parents=True, exist_ok=True)
    (SERIES_HTML_META_DIR / "finals_mvp.html").write_text(html, encoding="utf-8")
    df = pd.read_html(io.StringIO(html))[0]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
    out = META_DIR / "finals_mvp.csv"
    df.to_csv(out)
    print(f"Updated {out} ({len(df)} rows); latest={df.iloc[0].to_dict()}")


def update_champions_list(series_list: list[dict]) -> None:
    """Rebuild champions.csv newest-first to match finals_mvp.csv."""
    path = META_DIR / "champions.csv"
    mvp = pd.read_csv(META_DIR / "finals_mvp.csv", index_col=0)
    ids = pd.read_csv(META_DIR / "nba_team_ids_simple.csv")
    abbrev_map = dict(zip(ids["BBRef_Team_Abbreviation"], ids["BBRef_Team_Name"]))
    abbrev_map.update({s["winner_abbrev"]: s["winner_name"] for s in series_list})
    abbrev_map["OKC"] = "Oklahoma City Thunder"
    abbrev_map["NYK"] = "New York Knicks"

    names = []
    for _, row in mvp.iterrows():
        tm = row["Tm"]
        name = abbrev_map.get(tm)
        if name is None:
            raise KeyError(f"No team name mapping for abbrev {tm}")
        names.append(name)

    out_df = pd.DataFrame({"Team": names})
    out_df.to_csv(path)
    print(f"Updated {path} ({len(out_df)} rows); head={names[:4]}")


def save_team_meta(abbrev: str, year: int) -> None:
    from helpers.naming import team_html_name

    url = f"{BASE}/teams/{abbrev}/{year}.html"
    html = fetch(url)
    page = BeautifulSoup(html, "html.parser")
    meta = page.find(id="meta")
    if meta is None:
        raise ValueError(f"No #meta on {url}")
    TEAMS_HTML_DIR.mkdir(parents=True, exist_ok=True)
    out = TEAMS_HTML_DIR / team_html_name(abbrev, year)
    out.write_text(str(meta), encoding="utf-8")
    print(f"  wrote {out}")


def main() -> None:
    SERIES_HTML_FINALS_DIR.mkdir(parents=True, exist_ok=True)
    SERIES_HTML_META_DIR.mkdir(parents=True, exist_ok=True)
    TEAMS_HTML_DIR.mkdir(parents=True, exist_ok=True)

    for s in SERIES:
        url = f"{BASE}/playoffs/{s['slug']}.html"
        path = SERIES_HTML_FINALS_DIR / series_filename(s["slug"])
        if path.exists():
            html = path.read_text(encoding="utf-8")
            print(f"Using cached {path}")
        else:
            html = fetch(url)
            path.write_text(html, encoding="utf-8")
            print(f"Cached {path}")
        save_series_tables(s, html)
        save_team_meta(s["winner_abbrev"], s["year"])

    refresh_finals_mvp()
    update_champions_list(SERIES)
    print("Done scrape. Run scripts/parse_team_meta.py next.")


if __name__ == "__main__":
    main()
