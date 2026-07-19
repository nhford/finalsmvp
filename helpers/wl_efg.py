"""Parse Finals game boxes into win/loss eFG% splits (no network)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from helpers.boxscores import normalize_player_name
from helpers.paths import FINALS_WL_EFG_BY_SERIES_CSV
from helpers.q4 import (
    clean_q4_table,
    date_from_game_id,
    efg_pct,
    extract_table_from_div,
    series_stem_from_path,
)

_TEAM_HREF_RE = re.compile(r"^/teams/(?P<abbrev>[A-Z]{3})/\d{4}\.html$")
_GAME_BASIC_DIV_RE = re.compile(r"^all_box-(?P<abbrev>[A-Z]{3})-game-basic$")

_GAME_COLS = [
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


def game_basic_team_abbrevs(page: BeautifulSoup) -> list[str]:
    abbrevs: list[str] = []
    for tag in page.find_all(id=True):
        m = _GAME_BASIC_DIV_RE.match(tag["id"])
        if m:
            abbrevs.append(m.group("abbrev"))
    seen: set[str] = set()
    out: list[str] = []
    for a in abbrevs:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def parse_game_scores(html: str) -> dict[str, int]:
    """Return ``{team_abbrev: points}`` from the scorebox."""
    page = BeautifulSoup(html, "html.parser")
    sb = page.find("div", class_="scorebox")
    if sb is None:
        return {}
    scores: dict[str, int] = {}
    for team_div in sb.find_all("div", class_="scorebox_team"):
        abbrev = None
        for link in team_div.find_all("a", href=True):
            m = _TEAM_HREF_RE.match(link["href"])
            if m:
                abbrev = m.group("abbrev")
                break
        if abbrev is None:
            continue
        score_el = team_div.find("div", class_="score")
        if score_el is None:
            continue
        try:
            pts = int(score_el.get_text(strip=True))
        except ValueError:
            continue
        scores[abbrev] = pts
    return scores


def parse_game_wl(html: str) -> pd.DataFrame:
    """Parse both teams' full-game basic boxes and mark team win/loss."""
    page = BeautifulSoup(html, "html.parser")
    scores = parse_game_scores(html)
    if len(scores) < 2:
        return pd.DataFrame(columns=_GAME_COLS)

    max_pts = max(scores.values())
    frames: list[pd.DataFrame] = []
    for abbrev in game_basic_team_abbrevs(page):
        if abbrev not in scores:
            continue
        raw = extract_table_from_div(page, f"all_box-{abbrev}-game-basic")
        if raw is None:
            continue
        box = clean_q4_table(raw, abbrev)
        if box.empty:
            continue
        if "3P" not in box.columns:
            box["3P"] = 0.0
        else:
            box["3P"] = pd.to_numeric(box["3P"], errors="coerce").fillna(0.0)
        for col in ("FG", "FGA", "PTS"):
            if col in box.columns:
                box[col] = pd.to_numeric(box[col], errors="coerce")
        box["Won"] = bool(scores[abbrev] == max_pts and scores[abbrev] > min(scores.values()))
        box["eFG%"] = box.apply(
            lambda r: efg_pct(r.get("FG"), r.get("FGA"), r.get("3P", 0.0)),
            axis=1,
        )
        frames.append(box)

    if not frames:
        return pd.DataFrame(columns=_GAME_COLS)
    out = pd.concat(frames, ignore_index=True)
    keep = [c for c in _GAME_COLS if c in out.columns]
    return out[keep]


def aggregate_series_wl_efg(game_df: pd.DataFrame) -> pd.DataFrame:
    """Pool FG/FGA/3P by win/loss; compute ``rel_WL_eFG% = eFG%_W − eFG%_L``."""
    empty_cols = [
        "Year",
        "Series",
        "Team",
        "Player",
        "W_FG",
        "W_FGA",
        "W_3P",
        "W_eFG%",
        "L_FG",
        "L_FGA",
        "L_3P",
        "L_eFG%",
        "rel_WL_eFG%",
        "W_G",
        "L_G",
    ]
    if game_df.empty:
        return pd.DataFrame(columns=empty_cols)

    work = game_df.copy()
    for col in ("FG", "FGA", "3P", "PTS"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)
        elif col == "3P":
            work["3P"] = 0.0
    work["Won"] = work["Won"].astype(bool)

    keys = ["Year", "Series", "Team", "Player"]

    def _side(mask: pd.Series, prefix: str) -> pd.DataFrame:
        side = work.loc[mask]
        if side.empty:
            return pd.DataFrame(columns=keys + [f"{prefix}_FG", f"{prefix}_FGA", f"{prefix}_3P", f"{prefix}_G"])
        grouped = (
            side.groupby(keys, as_index=False)
            .agg(
                **{
                    f"{prefix}_FG": ("FG", "sum"),
                    f"{prefix}_FGA": ("FGA", "sum"),
                    f"{prefix}_3P": ("3P", "sum"),
                    f"{prefix}_G": ("Game", "nunique"),
                }
            )
        )
        return grouped

    wins = _side(work["Won"], "W")
    losses = _side(~work["Won"], "L")
    merged = wins.merge(losses, on=keys, how="outer")
    for col in ("W_FG", "W_FGA", "W_3P", "L_FG", "L_FGA", "L_3P", "W_G", "L_G"):
        if col not in merged.columns:
            merged[col] = 0.0
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)

    merged["W_eFG%"] = merged.apply(
        lambda r: efg_pct(r["W_FG"], r["W_FGA"], r["W_3P"]),
        axis=1,
    )
    merged["L_eFG%"] = merged.apply(
        lambda r: efg_pct(r["L_FG"], r["L_FGA"], r["L_3P"]),
        axis=1,
    )

    w_efg = pd.to_numeric(merged["W_eFG%"], errors="coerce")
    l_efg = pd.to_numeric(merged["L_eFG%"], errors="coerce")
    both = merged["W_FGA"].gt(0) & merged["L_FGA"].gt(0) & w_efg.notna() & l_efg.notna()
    rel = pd.Series(0.0, index=merged.index)
    rel.loc[both] = (w_efg.loc[both] - l_efg.loc[both]).round(3)
    merged["rel_WL_eFG%"] = rel

    return (
        merged[empty_cols]
        .sort_values(
            ["Year", "Series", "W_FGA", "L_FGA"],
            ascending=[False, True, False, False],
        )
        .reset_index(drop=True)
    )


def attach_rel_wl_efg(
    df: pd.DataFrame,
    year: int,
    wl_path: str = FINALS_WL_EFG_BY_SERIES_CSV,
    fill: float = 0.0,
) -> pd.DataFrame:
    """Add ``rel_WL_eFG%`` = eFG% in team wins − eFG% in team losses.

    Fill ``fill`` when the series CSV is missing, the year has no rows, or the
    player lacks FGA on either the win or loss side (sweeps, one-sided sample).
    """
    out = df.copy()
    out["rel_WL_eFG%"] = float(fill)

    path = Path(wl_path)
    if not path.exists():
        return out

    wl = pd.read_csv(path)
    need = ["Player", "rel_WL_eFG%", "W_FGA", "L_FGA"]
    missing = [c for c in need if c not in wl.columns]
    if missing:
        raise KeyError(f"{wl_path} missing {missing}; re-run scripts/extract_wl_efg.py")
    wl = wl.loc[wl["Year"] == year, need].copy()
    if wl.empty:
        return out

    wl["_player_key"] = wl["Player"].map(normalize_player_name)
    # Prefer the larger combined sample if a name collides across teams (rare).
    wl["_sample"] = (
        pd.to_numeric(wl["W_FGA"], errors="coerce").fillna(0)
        + pd.to_numeric(wl["L_FGA"], errors="coerce").fillna(0)
    )
    wl = wl.sort_values("_sample", ascending=False).drop_duplicates(
        "_player_key", keep="first"
    )
    wl["rel_WL_eFG%"] = pd.to_numeric(wl["rel_WL_eFG%"], errors="coerce")

    out["_player_key"] = out["Player"].map(normalize_player_name)
    merged = out.merge(
        wl[["_player_key", "rel_WL_eFG%"]].rename(columns={"rel_WL_eFG%": "_rel_wl"}),
        on="_player_key",
        how="left",
    )
    rel = pd.to_numeric(merged["_rel_wl"], errors="coerce").fillna(fill)
    out["rel_WL_eFG%"] = rel.round(3).to_numpy()
    return out.drop(columns=["_player_key"])


__all__ = [
    "aggregate_series_wl_efg",
    "attach_rel_wl_efg",
    "date_from_game_id",
    "game_basic_team_abbrevs",
    "parse_game_scores",
    "parse_game_wl",
    "series_stem_from_path",
]
