"""Canonical local filenames for scraped HTML / derived CSVs.

Conventions
-----------
Finals series pages / box-score CSVs share one stem::

    {year}_nba_finals_{team_a}_vs_{team_b}

Team season meta HTML::

    {ABBREV}_{year}.html          e.g. BOS_2024.html

Series-index / award pages (under data/series_html/meta/)::

    finals_mvp.html
    playoffs_series.html
"""

from __future__ import annotations

import re
from pathlib import Path


FINALS_STEM_RE = re.compile(
    r"^(?P<year>\d{4})_nba_finals_(?P<a>.+)_vs_(?P<b>.+)$"
)
TEAM_HTML_STEM_RE = re.compile(r"^(?P<abbrev>[A-Z]{3})_(?P<year>\d{4})$")
# Legacy cramped form produced by older scrapers
TEAM_HTML_STEM_LEGACY_RE = re.compile(r"^(?P<abbrev>[A-Z]{3})(?P<year>\d{4})$")


def bbr_slug_to_stem(slug_or_url: str) -> str:
    """Turn a BBR path/slug into our underscore stem (no extension)."""
    leaf = slug_or_url.rstrip("/").split("/")[-1]
    leaf = leaf.replace(".html", "").replace(".csv", "")
    return leaf.replace("-", "_")


def finals_html_name(slug_or_url: str) -> str:
    return f"{bbr_slug_to_stem(slug_or_url)}.html"


def finals_csv_name(slug_or_url: str) -> str:
    return f"{bbr_slug_to_stem(slug_or_url)}.csv"


def team_html_name(abbrev: str, year: int | str) -> str:
    return f"{abbrev.upper()}_{int(year)}.html"


def team_html_name_from_url(team_url: str) -> str:
    """https://.../teams/BOS/2024.html → BOS_2024.html"""
    parts = team_url.rstrip("/").split("/")
    # .../teams/{ABBREV}/{year}.html
    abbrev = parts[-2]
    year = parts[-1].replace(".html", "")
    return team_html_name(abbrev, year)


def parse_team_html_stem(stem: str) -> tuple[str | None, int | None]:
    """Parse BOS_2024 or legacy BOS2024 → (abbrev, year)."""
    m = TEAM_HTML_STEM_RE.match(stem) or TEAM_HTML_STEM_LEGACY_RE.match(stem)
    if not m:
        return None, None
    return m.group("abbrev"), int(m.group("year"))


def is_finals_stem(stem: str) -> bool:
    return bool(FINALS_STEM_RE.match(Path(stem).stem if "." in stem else stem))
