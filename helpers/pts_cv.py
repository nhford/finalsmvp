"""Per-game points coefficient of variation (scoring consistency)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from helpers.boxscores import normalize_player_name
from helpers.paths import FINALS_PTS_CV_BY_SERIES_CSV


def _pts_cv(pts: pd.Series) -> float:
    """Sample CV = std(PTS) / mean(PTS); 0 if undefined (<2 games or mean ≤ 0)."""
    values = pd.to_numeric(pts, errors="coerce").dropna()
    if len(values) < 2:
        return 0.0
    mean = float(values.mean())
    if mean <= 0:
        return 0.0
    std = float(values.std(ddof=1))
    if pd.isna(std):
        return 0.0
    return round(std / mean, 3)


def aggregate_series_pts_cv(game_df: pd.DataFrame) -> pd.DataFrame:
    """Per player-series: mean/std/CV of game PTS (from full-game boxes)."""
    empty_cols = [
        "Year",
        "Series",
        "Team",
        "Player",
        "PTS_mean",
        "PTS_std",
        "PTS_CV",
        "PTS_G",
    ]
    if game_df.empty:
        return pd.DataFrame(columns=empty_cols)

    work = game_df.copy()
    work["PTS"] = pd.to_numeric(work["PTS"], errors="coerce")
    rows: list[dict] = []
    keys = ["Year", "Series", "Team", "Player"]
    for key, group in work.groupby(keys, sort=False):
        pts = group["PTS"].dropna()
        n = int(pts.shape[0])
        mean = float(pts.mean()) if n else 0.0
        std = float(pts.std(ddof=1)) if n >= 2 else 0.0
        if pd.isna(std):
            std = 0.0
        year, series, team, player = key
        rows.append(
            {
                "Year": year,
                "Series": series,
                "Team": team,
                "Player": player,
                "PTS_mean": round(mean, 3),
                "PTS_std": round(std, 3),
                "PTS_CV": _pts_cv(pts),
                "PTS_G": n,
            }
        )

    return (
        pd.DataFrame(rows, columns=empty_cols)
        .sort_values(
            ["Year", "Series", "PTS_mean", "Player"],
            ascending=[False, True, False, True],
        )
        .reset_index(drop=True)
    )


def attach_pts_cv(
    df: pd.DataFrame,
    year: int,
    pts_cv_path: str = FINALS_PTS_CV_BY_SERIES_CSV,
    fill: float = 0.0,
) -> pd.DataFrame:
    """Add ``PTS_CV`` = std(per-game PTS) / mean(per-game PTS).

    Scale-free scoring volatility — orthogonal to series ``PTS`` total. Fill
    ``fill`` when the series CSV is missing, the year has no rows, or the
    player has fewer than two scored games.
    """
    out = df.copy()
    out["PTS_CV"] = float(fill)

    path = Path(pts_cv_path)
    if not path.exists():
        return out

    cv = pd.read_csv(path)
    need = ["Player", "PTS_CV", "PTS_G"]
    missing = [c for c in need if c not in cv.columns]
    if missing:
        raise KeyError(
            f"{pts_cv_path} missing {missing}; re-run scripts/extract_wl_efg.py"
        )
    cv = cv.loc[cv["Year"] == year, need].copy()
    if cv.empty:
        return out

    cv["_player_key"] = cv["Player"].map(normalize_player_name)
    cv = cv.sort_values("PTS_G", ascending=False).drop_duplicates(
        "_player_key", keep="first"
    )
    cv["PTS_CV"] = pd.to_numeric(cv["PTS_CV"], errors="coerce")

    out["_player_key"] = out["Player"].map(normalize_player_name)
    merged = out.merge(
        cv[["_player_key", "PTS_CV"]].rename(columns={"PTS_CV": "_pts_cv"}),
        on="_player_key",
        how="left",
    )
    rel = pd.to_numeric(merged["_pts_cv"], errors="coerce").fillna(fill)
    out["PTS_CV"] = rel.round(3).to_numpy()
    return out.drop(columns=["_player_key"])


__all__ = [
    "aggregate_series_pts_cv",
    "attach_pts_cv",
]
