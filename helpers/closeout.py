"""Closeout-game points relative to other games in the series."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from helpers.boxscores import normalize_player_name
from helpers.paths import FINALS_CLOSEOUT_PTS_BY_SERIES_CSV


def aggregate_series_closeout_pts(game_df: pd.DataFrame) -> pd.DataFrame:
    """Per player-series: closeout PTS minus mean PTS in other games.

    Closeout = the series' last game (max ``Game``). Players who miss the
    closeout or have no other scored games get ``rel_closeout_PTS = 0``.
    """
    empty_cols = [
        "Year",
        "Series",
        "Team",
        "Player",
        "Closeout_Game",
        "Closeout_PTS",
        "Other_PTS_mean",
        "Other_G",
        "rel_closeout_PTS",
    ]
    if game_df.empty:
        return pd.DataFrame(columns=empty_cols)

    work = game_df.copy()
    work["PTS"] = pd.to_numeric(work["PTS"], errors="coerce")
    work["Game"] = pd.to_numeric(work["Game"], errors="coerce")

    closeout_game = work.groupby(["Year", "Series"], sort=False)["Game"].transform("max")
    work["_is_closeout"] = work["Game"].eq(closeout_game)

    rows: list[dict] = []
    keys = ["Year", "Series", "Team", "Player"]
    for key, group in work.groupby(keys, sort=False):
        year, series, team, player = key
        close = group.loc[group["_is_closeout"], "PTS"].dropna()
        other = group.loc[~group["_is_closeout"], "PTS"].dropna()
        closeout_g = int(group["Game"].max()) if group["Game"].notna().any() else 0

        if close.empty or other.empty:
            rel = 0.0
            close_pts = float(close.iloc[0]) if len(close) else 0.0
            other_mean = float(other.mean()) if len(other) else 0.0
        else:
            close_pts = float(close.iloc[0])
            other_mean = float(other.mean())
            rel = round(close_pts - other_mean, 3)

        rows.append(
            {
                "Year": year,
                "Series": series,
                "Team": team,
                "Player": player,
                "Closeout_Game": closeout_g,
                "Closeout_PTS": round(close_pts, 3),
                "Other_PTS_mean": round(other_mean, 3),
                "Other_G": int(other.shape[0]),
                "rel_closeout_PTS": rel,
            }
        )

    return (
        pd.DataFrame(rows, columns=empty_cols)
        .sort_values(
            ["Year", "Series", "Closeout_PTS", "Player"],
            ascending=[False, True, False, True],
        )
        .reset_index(drop=True)
    )


def attach_rel_closeout_pts(
    df: pd.DataFrame,
    year: int,
    closeout_path: str = FINALS_CLOSEOUT_PTS_BY_SERIES_CSV,
    fill: float = 0.0,
) -> pd.DataFrame:
    """Add ``rel_closeout_PTS`` = closeout PTS − mean PTS in other games.

    Fill ``fill`` when the series CSV is missing, the year has no rows, the
    player missed the closeout, or they have no other games to compare against.
    """
    out = df.copy()
    out["rel_closeout_PTS"] = float(fill)

    path = Path(closeout_path)
    if not path.exists():
        return out

    close = pd.read_csv(path)
    need = ["Player", "rel_closeout_PTS", "Other_G", "Closeout_PTS"]
    missing = [c for c in need if c not in close.columns]
    if missing:
        raise KeyError(
            f"{closeout_path} missing {missing}; re-run scripts/extract_wl_efg.py"
        )
    close = close.loc[close["Year"] == year, need].copy()
    if close.empty:
        return out

    close["_player_key"] = close["Player"].map(normalize_player_name)
    # Prefer the larger non-closeout sample if a name collides across teams.
    close = close.sort_values("Other_G", ascending=False).drop_duplicates(
        "_player_key", keep="first"
    )
    close["rel_closeout_PTS"] = pd.to_numeric(close["rel_closeout_PTS"], errors="coerce")

    out["_player_key"] = out["Player"].map(normalize_player_name)
    merged = out.merge(
        close[["_player_key", "rel_closeout_PTS"]].rename(
            columns={"rel_closeout_PTS": "_rel_closeout"}
        ),
        on="_player_key",
        how="left",
    )
    rel = pd.to_numeric(merged["_rel_closeout"], errors="coerce").fillna(fill)
    out["rel_closeout_PTS"] = rel.round(3).to_numpy()
    return out.drop(columns=["_player_key"])


__all__ = [
    "aggregate_series_closeout_pts",
    "attach_rel_closeout_pts",
]
