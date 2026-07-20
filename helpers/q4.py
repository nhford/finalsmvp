"""Parse Basketball-Reference per-game Q4 box scores (no network)."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, Comment

from helpers.boxscores import fix_player_name_encoding, normalize_player_name
from helpers.paths import FINALS_Q4_BY_SERIES_CSV

# BR quarterly player boxes are available from the 1996-97 season onward.
Q4_MIN_YEAR = 1997

_SKIP_PLAYERS = {"", "reserves", "starters", "team totals"}
_BOX_ID_RE = re.compile(r"^/boxscores/(?P<game_id>\d{8}0[A-Z]{3})\.html$")
_Q4_DIV_RE = re.compile(r"^all_box-(?P<abbrev>[A-Z]{3})-q4-basic$")


def game_links_from_series_html(html: str) -> list[str]:
    """Return ordered unique /boxscores/….html hrefs from a Finals series page."""
    page = BeautifulSoup(html, "html.parser")
    summaries = page.find(id="div_other_scores")
    if summaries is None:
        return []
    links: list[str] = []
    seen: set[str] = set()
    for tag in summaries.find_all("a"):
        href = tag.get("href") or ""
        if "boxscore" not in href or not href.endswith(".html"):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append(href)
    return links


def parse_box_game_id(href: str) -> str | None:
    m = _BOX_ID_RE.match(href)
    return m.group("game_id") if m else None


def date_from_game_id(game_id: str) -> str:
    """202406060BOS → 2024-06-06."""
    return f"{game_id[:4]}-{game_id[4:6]}-{game_id[6:8]}"


def extract_table_from_div(page: BeautifulSoup, div_id: str) -> pd.DataFrame | None:
    container = page.find(id=div_id)
    if container is None:
        return None
    table = container.find("table")
    if table is None:
        for comment in container.find_all(string=lambda t: isinstance(t, Comment)):
            inner = BeautifulSoup(comment, "html.parser")
            table = inner.find("table")
            if table is not None:
                break
    if table is None:
        return None
    dfs = pd.read_html(io.StringIO(str(table)))
    if not dfs:
        return None
    df = dfs[0]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            c[-1] if isinstance(c, tuple) else c for c in df.columns.to_flat_index()
        ]
    return df


def q4_team_abbrevs(page: BeautifulSoup) -> list[str]:
    abbrevs: list[str] = []
    for tag in page.find_all(id=True):
        m = _Q4_DIV_RE.match(tag["id"])
        if m:
            abbrevs.append(m.group("abbrev"))
    # Preserve document order, unique
    seen: set[str] = set()
    out: list[str] = []
    for a in abbrevs:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def clean_q4_table(df: pd.DataFrame, team: str) -> pd.DataFrame:
    """Normalize a Q4 basic box into Player / FG / FGA / … rows."""
    work = df.copy()
    # BR labels the player column "Starters" (with a Reserves banner row).
    player_col = None
    for cand in ("Starters", "Reserves", "Player"):
        if cand in work.columns:
            player_col = cand
            break
    if player_col is None:
        player_col = work.columns[0]

    work = work.rename(columns={player_col: "Player"})
    work["Player"] = work["Player"].map(
        lambda v: fix_player_name_encoding(str(v)) if pd.notna(v) else ""
    )
    work = work[
        ~work["Player"].str.strip().str.casefold().isin(_SKIP_PLAYERS)
    ].copy()
    work = work[work["Player"].str.strip() != ""].copy()

    for col in ("FG", "FGA", "3P", "3PA", "FT", "FTA", "PTS"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    # Drop DNP / empty Q4 rows (BR leaves a name with a blank reason colspan).
    if {"FG", "FGA"}.issubset(work.columns):
        work = work[work["FG"].notna() | work["FGA"].notna()].copy()

    keep = [
        c
        for c in ("Player", "MP", "FG", "FGA", "FG%", "3P", "3PA", "FT", "FTA", "PTS")
        if c in work.columns
    ]
    out = work[keep].copy()
    out.insert(0, "Team", team)
    return out.reset_index(drop=True)


def parse_game_q4(html: str) -> pd.DataFrame:
    """Parse both teams' Q4 basic boxes from a game box-score page."""
    page = BeautifulSoup(html, "html.parser")
    frames: list[pd.DataFrame] = []
    for abbrev in q4_team_abbrevs(page):
        raw = extract_table_from_div(page, f"all_box-{abbrev}-q4-basic")
        if raw is None:
            continue
        frames.append(clean_q4_table(raw, abbrev))
    if not frames:
        return pd.DataFrame(
            columns=[
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
        )
    return pd.concat(frames, ignore_index=True)


def efg_pct(fg: float, fga: float, three_p: float):
    """Effective FG%: (FG + 0.5 * 3P) / FGA."""
    if fga is None or pd.isna(fga) or float(fga) <= 0:
        return pd.NA
    return round((float(fg) + 0.5 * float(three_p)) / float(fga), 3)


def aggregate_series_q4(game_df: pd.DataFrame) -> pd.DataFrame:
    """Sum Q4 FG/FGA/3P/PTS across games; compute Q4_FG% and Q4_eFG%."""
    if game_df.empty:
        return pd.DataFrame(
            columns=[
                "Year",
                "Series",
                "Team",
                "Player",
                "Q4_FG",
                "Q4_FGA",
                "Q4_3P",
                "Q4_FG%",
                "Q4_eFG%",
                "Q4_PTS",
                "Q4_G",
            ]
        )
    work = game_df.copy()
    for col in ("FG", "FGA", "3P", "PTS"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    grouped = (
        work.groupby(["Year", "Series", "Team", "Player"], as_index=False)
        .agg(
            Q4_FG=("FG", "sum"),
            Q4_FGA=("FGA", "sum"),
            Q4_3P=("3P", "sum"),
            Q4_PTS=("PTS", "sum"),
            Q4_G=("Game", "nunique"),
        )
    )
    grouped["Q4_FG%"] = grouped.apply(
        lambda r: round(r["Q4_FG"] / r["Q4_FGA"], 3) if r["Q4_FGA"] else pd.NA,
        axis=1,
    )
    grouped["Q4_eFG%"] = grouped.apply(
        lambda r: efg_pct(r["Q4_FG"], r["Q4_FGA"], r["Q4_3P"]),
        axis=1,
    )
    return grouped.sort_values(
        ["Year", "Series", "Q4_FGA", "Q4_FG"], ascending=[False, True, False, False]
    ).reset_index(drop=True)


def series_stem_from_path(path: str | Path) -> str:
    return Path(path).name.replace(".html", "").replace(".csv", "")


def attach_rel_q4_efg(
    df: pd.DataFrame,
    year: int,
    q4_path: str = FINALS_Q4_BY_SERIES_CSV,
    fill: float = 0.0,
) -> pd.DataFrame:
    """Add ``rel_Q4_eFG%`` = series Q4 eFG% − series eFG%.

    eFG% = (FG + 0.5 * 3P) / FGA. Basketball-Reference Q4 player boxes start
    in 1997; earlier years (or players with no Q4 FGA) get ``fill``.
    """
    if "eFG%" not in df.columns:
        raise KeyError("attach_rel_q4_efg requires eFG% on the box-score frame")

    out = df.copy()
    out["rel_Q4_eFG%"] = float(fill)

    path = Path(q4_path)
    if not path.exists() or year < Q4_MIN_YEAR:
        return out

    q4 = pd.read_csv(path)
    need = ["Player", "Q4_eFG%", "Q4_FGA"]
    missing = [c for c in need if c not in q4.columns]
    if missing:
        raise KeyError(f"{q4_path} missing {missing}; re-run scripts/extract_q4.py")
    q4 = q4.loc[q4["Year"] == year, need].copy()
    if q4.empty:
        return out

    q4["_player_key"] = q4["Player"].map(normalize_player_name)
    # Prefer the larger Q4 sample if a name collides across teams (rare).
    q4 = q4.sort_values("Q4_FGA", ascending=False).drop_duplicates(
        "_player_key", keep="first"
    )
    q4["Q4_eFG%"] = pd.to_numeric(q4["Q4_eFG%"], errors="coerce")

    out["_player_key"] = out["Player"].map(normalize_player_name)
    merged = out.merge(
        q4[["_player_key", "Q4_eFG%"]],
        on="_player_key",
        how="left",
    )
    series_efg = pd.to_numeric(merged["eFG%"], errors="coerce")
    q4_efg = pd.to_numeric(merged["Q4_eFG%"], errors="coerce")
    rel = (q4_efg - series_efg).fillna(fill)
    out["rel_Q4_eFG%"] = rel.round(3).to_numpy()
    return out.drop(columns=["_player_key"])


# Back-compat alias
attach_rel_q4_fg = attach_rel_q4_efg