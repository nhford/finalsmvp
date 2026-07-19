"""Lookups against finals MVP / champions / team-id CSVs."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from bs4 import BeautifulSoup

from helpers.paths import (
    BASE_URL,
    CHAMPIONS_CSV,
    CHAMPIONS_SEASONS_CSV,
    FINALS_MVP_CSV,
    TEAM_IDS_SIMPLE_CSV,
    TEAMS_HTML_DIR,
)


def year_from_url(url: str) -> int:
    return int(url.split("/")[-1].split("-")[0])


@lru_cache(maxsize=1)
def _finals_mvp_df(path: str = FINALS_MVP_CSV) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0)


@lru_cache(maxsize=1)
def _champions_df(path: str = CHAMPIONS_CSV) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0)


@lru_cache(maxsize=1)
def _team_ids_df(path: str = TEAM_IDS_SIMPLE_CSV) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0)


def _season_label(year: int) -> str:
    """Map Finals calendar year -> Basketball-Reference Season (e.g. 2024 -> 2023-24)."""
    return f"{year - 1}-{str(year)[-2:]}"


def latest_finals_year(path: str = FINALS_MVP_CSV) -> int:
    """Newest Finals year in finals_mvp.csv (row 0 Season end year)."""
    season = str(_finals_mvp_df(path)["Season"].iloc[0])
    start = int(season.split("-")[0])
    return start + 1


def mvp_from_year(year: int, path: str = FINALS_MVP_CSV) -> str:
    df = _finals_mvp_df(path)
    season = _season_label(year)
    matches = df.loc[df["Season"] == season, "Player"]
    if len(matches):
        return matches.iloc[0]
    return df["Player"].iloc[latest_finals_year(path) - year]


def champ_from_year(year: int, path: str = CHAMPIONS_CSV) -> str:
    df = _champions_df(path)
    return df["Team"].iloc[latest_finals_year() - year]


def mvp_from_url(url: str, path: str = FINALS_MVP_CSV) -> str:
    return mvp_from_year(year_from_url(url), path=path)


def abbrev_from_team(team_name: str, path: str = TEAM_IDS_SIMPLE_CSV) -> str:
    mapping = _team_ids_df(path)
    row = mapping[mapping["BBRef_Team_Name"].str.contains(team_name, na=False)]
    return row["BBRef_Team_Abbreviation"].values[0]


def espn_abbrev_from_team(team_name: str, path: str = TEAM_IDS_SIMPLE_CSV) -> str:
    mapping = _team_ids_df(path)
    row = mapping[mapping["BBRef_Team_Name"].str.contains(team_name, na=False)]
    return row["ESPN_Current_Link_ID"].values[0]


def logo(team: str) -> str:
    abbrev = espn_abbrev_from_team(team.strip())
    return f"https://a.espncdn.com/i/teamlogos/nba/500/{abbrev}.png"


def url_from_abbrev_and_year(abbrev: str, year: int) -> str:
    return f"{BASE_URL}/teams/{abbrev}/{year}.html"


def name_team(team_url: str) -> str:
    """Local cache filename for a team season page (BOS_2024.html)."""
    from helpers.naming import team_html_name_from_url

    return team_html_name_from_url(team_url)


def logo_from_seasons_csv(
    team_name: str,
    year: int,
    path: str = CHAMPIONS_SEASONS_CSV,
) -> str | None:
    """Prefer committed champions_seasons.csv so analysis needs no HTML cache."""
    try:
        seasons = pd.read_csv(path)
    except FileNotFoundError:
        return None
    match = seasons[(seasons["year"] == year) & (seasons["team"] == team_name)]
    if match.empty or pd.isna(match.iloc[0].get("logo_url")):
        return None
    return match.iloc[0]["logo_url"]


def logo_from_url(url: str, teams_html_dir: str = TEAMS_HTML_DIR) -> str:
    """Fallback: scrape #meta from a team page (requires network + HTML cache)."""
    from helpers.scrape import save_tag

    save_tag(url, teams_html_dir, "meta", name_fn=name_team)
    content = BeautifulSoup(
        save_tag(url, teams_html_dir, "meta", name_fn=name_team),
        "html.parser",
    )
    return content.find("img")["src"]


def logo_from_team_name(team_name: str, year: int) -> str:
    cached = logo_from_seasons_csv(team_name, year)
    if cached:
        return cached
    abbrev = abbrev_from_team(team_name)
    url = url_from_abbrev_and_year(abbrev, year)
    return logo_from_url(url)
