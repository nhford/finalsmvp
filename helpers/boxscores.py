"""Load and feature-engineer Finals box-score CSVs (no HTML / network)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

from helpers.meta import champ_from_year, mvp_from_year
from helpers.paths import (
    FINALS_SERIES_GAMES_CSV,
    SERIES_TABLES_ADVANCED_WINNER_DIR,
    SERIES_TABLES_WINNER_DIR,
)

# Available on Basketball-Reference advanced series tables from 1984 on.
ADVANCED_FEATURE_COLS = ("USG%", "TRB%", "AST%", "TOV%", "ORtg", "DRtg")
# Derived after join: NetRtg = ORtg − DRtg; AST%-TOV% = AST% − TOV%.
ADVANCED_DERIVED_COLS = ("NetRtg", "AST%-TOV%")

# Lean logistic feature set: usage/minutes, rates, secondary stats, GM.
# Drops collinear counting stats (FG/FT/ORB/DRB/TRB/AST/STL/BLK/PF/G/3P/FT%/TOV).
# PTS_CV = std(per-game PTS) / mean(per-game PTS) — scale-free consistency.
# rel_closeout_PTS = closeout PTS − mean PTS in other series games.
# NetRtg replaces separate ORtg / DRtg; AST%-TOV% replaces raw TOV%.
LEAN_MODEL_FEATURE_COLS = (
    "USG%",
    "PTS_CV",
    "rel_closeout_PTS",
    "eFG%",
    "rel_Q4_eFG%",
    "rel_WL_eFG%",
    "TRB%",
    "AST%-TOV%",
    "NetRtg",
    "MP",
    "GM",
)

_SUFFIXES = (" jr.", " sr.", " iii", " ii", " iv", " jr", " sr")


def fix_player_name_encoding(value: str) -> str:
    """Repair double-encoded UTF-8 (mojibake) in scraped player names."""
    text = str(value).strip()
    for _ in range(3):
        try:
            nxt = text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if nxt == text:
            break
        text = nxt
    return text


def normalize_player_name(value: str) -> str:
    """Canonical key for joining player names across tables.

    Handles mojibake, accents (Jokić/Jokic, Porziņģis/Porzingis), case, and
    common generational suffixes.
    """
    text = fix_player_name_encoding(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split()).casefold()
    for suffix in _SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].rstrip()
            break
    return text


# Back-compat alias used by MVP / baseline comparisons
_norm_name = normalize_player_name


def year_from_series_csv(path: str | Path) -> int:
    return int(Path(path).name.split("_")[0])


def series_games_from_boxscore(df: pd.DataFrame) -> int:
    """Series length = max games played by any player on the roster table."""
    if "G" not in df.columns:
        raise KeyError("box score missing G column")
    games = pd.to_numeric(df["G"], errors="coerce")
    if games.isna().all():
        raise ValueError("box score has no numeric G values")
    return int(games.max())


def build_finals_series_games(
    winner_dir: str = SERIES_TABLES_WINNER_DIR,
) -> pd.DataFrame:
    """Year → Finals series length (games), derived from winner box scores."""
    rows = []
    for path in list_winner_csvs(winner_dir):
        year = year_from_series_csv(path)
        cleaned = clean_boxscore(load_winner_csv(path), year)
        rows.append({"Year": year, "Games": series_games_from_boxscore(cleaned)})
    return pd.DataFrame(rows).sort_values("Year", ascending=False).reset_index(drop=True)


def series_games_from_year(
    year: int,
    path: str = FINALS_SERIES_GAMES_CSV,
) -> int:
    """Look up Finals series length from ``data/meta/finals_series_games.csv``."""
    df = pd.read_csv(path)
    matches = df.loc[df["Year"] == year, "Games"]
    if matches.empty:
        raise KeyError(f"No series length for year {year} in {path}")
    return int(matches.iloc[0])


def select_model_features(
    players: pd.DataFrame,
    advanced: bool = True,
    feature_cols: tuple[str, ...] = LEAN_MODEL_FEATURE_COLS,
) -> pd.DataFrame:
    """Return Year/Player/mvp + lean model columns (optionally without advanced)."""
    cols = list(feature_cols)
    if not advanced:
        drop = set(ADVANCED_FEATURE_COLS) | set(ADVANCED_DERIVED_COLS)
        cols = [c for c in cols if c not in drop]
    missing = [c for c in cols if c not in players.columns]
    if missing:
        raise KeyError(f"Missing model feature columns: {missing}")
    return players[["Year", "Player", "mvp", *cols]].copy()


def load_winner_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.columns[0].startswith("Unnamed"):
        df = df.drop(columns=df.columns[0])
    if "Rk" in df.columns:
        df = df.drop(columns=["Rk"])
    if "Player" in df.columns:
        df["Player"] = df["Player"].map(
            lambda value: fix_player_name_encoding(value)
            if pd.notna(value) and str(value).lower() != "team totals"
            else value
        )
    return df


def clean_boxscore(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Drop per-game duplicates / rate denominators; label the Finals MVP."""
    mvp = mvp_from_year(year)
    t = df.copy()
    t = t[t["Player"].astype(str).str.lower() != "team totals"].copy()
    t = t[~t["Player"].isna()].copy()

    for col in ["3P", "STL", "BLK", "ORB", "DRB", "TOV", "G", "MP", "FG", "FGA", "FT", "TRB", "AST", "PF", "PTS"]:
        if col in t.columns:
            t[col] = pd.to_numeric(t[col], errors="coerce").fillna(0).astype(int)
    for col in ["FG%", "3P%", "FT%"]:
        if col in t.columns:
            t[col] = pd.to_numeric(t[col], errors="coerce").fillna(0).astype(float)

    # eFG% = (FG + 0.5 * 3P) / FGA — keep before dropping attempt denominators.
    if {"FG", "FGA", "3P"}.issubset(t.columns):
        t["eFG%"] = t.apply(
            lambda r: round((r["FG"] + 0.5 * r["3P"]) / r["FGA"], 3) if r["FGA"] else 0.0,
            axis=1,
        )

    drop = ["Age", "FGA", "3PA", "FTA"]
    per_game = [c for c in t.columns if str(c).endswith(".1")]
    t = t.drop(columns=[c for c in drop + per_game if c in t.columns], errors="ignore")

    mvp_n = _norm_name(mvp)
    t["mvp"] = t["Player"].apply(lambda x: x == mvp or _norm_name(x) == mvp_n)
    return t.reset_index(drop=True)


def rank_table(t: pd.DataFrame) -> pd.DataFrame:
    """Replace raw stats with within-team ranks (TOV/PF: lower is better)."""
    skip = {"Player", "mvp", "Series_G", "GM", "Year"}
    cols = [c for c in t.columns if c not in skip]
    out = t.copy()
    for col in cols:
        ascending = col in {"TOV", "PF"}
        out[f"{col}!"] = out[col].rank(ascending=ascending, method="min").astype(int)
        out.drop(columns=[col], inplace=True)
    return out


def load_advanced_features(
    path: str | Path,
    cols: tuple[str, ...] = ADVANCED_FEATURE_COLS,
) -> pd.DataFrame:
    """Load selected advanced box-score columns keyed by Player."""
    df = load_winner_csv(path)
    df = df[df["Player"].astype(str).str.lower() != "team totals"].copy()
    df = df[~df["Player"].isna()].copy()
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{path} missing advanced columns: {missing}")
    out = df[["Player", *cols]].copy()
    for col in cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.reset_index(drop=True)


def attach_advanced(
    df: pd.DataFrame,
    series_csv_name: str,
    advanced_dir: str = SERIES_TABLES_ADVANCED_WINNER_DIR,
    cols: tuple[str, ...] = ADVANCED_FEATURE_COLS,
) -> pd.DataFrame:
    """Left-join advanced features onto a top-N basic table for one series.

    Joins on ``normalize_player_name`` so ASCII / accented / mojibake variants
    of the same player match. Raises if any row fails to match — silent 0-fills
    previously made missing joins look like elite DRtg.
    """
    adv_path = Path(advanced_dir) / series_csv_name
    if not adv_path.exists():
        return df
    adv = load_advanced_features(adv_path, cols=cols).copy()
    left = df.copy()
    left["_player_key"] = left["Player"].map(normalize_player_name)
    adv["_player_key"] = adv["Player"].map(normalize_player_name)
    adv_keyed = adv.drop(columns=["Player"]).drop_duplicates("_player_key", keep="first")
    merged = left.merge(adv_keyed, on="_player_key", how="left")
    unmatched = merged[list(cols)].isna().any(axis=1)
    if unmatched.any():
        names = merged.loc[unmatched, "Player"].tolist()
        raise ValueError(
            f"Advanced join failed for {series_csv_name}: {names}. "
            "Check player-name encoding between basic and advanced CSVs."
        )
    return merged.drop(columns=["_player_key"])


def top_table_from_csv(
    path: str | Path,
    top: int = 8,
    rank: bool = True,
    advanced: bool = False,
    advanced_dir: str = SERIES_TABLES_ADVANCED_WINNER_DIR,
    advanced_cols: tuple[str, ...] = ADVANCED_FEATURE_COLS,
    q4: bool = True,
    wl: bool = True,
    pts_cv: bool = True,
    closeout: bool = True,
) -> pd.DataFrame:
    from helpers.closeout import attach_rel_closeout_pts
    from helpers.pts_cv import attach_pts_cv
    from helpers.q4 import attach_rel_q4_efg
    from helpers.wl_efg import attach_rel_wl_efg

    path = Path(path)
    year = year_from_series_csv(path)
    df = clean_boxscore(load_winner_csv(path), year)
    series_g = series_games_from_boxscore(df)
    df = df.iloc[:top].copy()
    games_missed = (series_g - df["G"]).astype(int)
    if q4:
        # Needs raw eFG%; attach before rank_table renames columns.
        df = attach_rel_q4_efg(df, year)
    if wl:
        df = attach_rel_wl_efg(df, year)
    if pts_cv:
        df = attach_pts_cv(df, year)
    if closeout:
        df = attach_rel_closeout_pts(df, year)
    if rank:
        df = rank_table(df)
    if advanced:
        df = attach_advanced(df, path.name, advanced_dir=advanced_dir, cols=advanced_cols)
        df["NetRtg"] = (
            pd.to_numeric(df["ORtg"], errors="coerce")
            - pd.to_numeric(df["DRtg"], errors="coerce")
        ).round(1)
        df["AST%-TOV%"] = (
            pd.to_numeric(df["AST%"], errors="coerce")
            - pd.to_numeric(df["TOV%"], errors="coerce")
        ).round(1)
    df.insert(0, "Year", year)
    df["Series_G"] = series_g
    df["GM"] = games_missed.to_numpy()
    return df


def list_winner_csvs(winner_dir: str = SERIES_TABLES_WINNER_DIR) -> list[Path]:
    return sorted(
        Path(winner_dir).glob("*_nba_finals_*.csv"),
        key=lambda p: p.name,
        reverse=True,
    )


def build_top8(
    winner_dir: str = SERIES_TABLES_WINNER_DIR,
    top: int = 8,
    rank: bool = True,
    advanced: bool = False,
    advanced_dir: str = SERIES_TABLES_ADVANCED_WINNER_DIR,
    advanced_cols: tuple[str, ...] = ADVANCED_FEATURE_COLS,
    require_advanced: bool = False,
    q4: bool = True,
    wl: bool = True,
    pts_cv: bool = True,
    closeout: bool = True,
) -> pd.DataFrame:
    """Stack top-N champion tables. Set ``advanced=True`` to add USG%/NetRtg/….

    When ``require_advanced`` is True, only series with an advanced CSV are kept
    (Basketball-Reference advanced Finals tables start in 1984).

    ``q4=True`` adds ``rel_Q4_eFG%`` (Q4 eFG% − series eFG%; 0 before 1997 / no Q4 FGA).
    ``wl=True`` adds ``rel_WL_eFG%`` (eFG% in team wins − eFG% in team losses; 0 if
    either side has no FGA).
    ``pts_cv=True`` adds ``PTS_CV`` (std/mean of per-game PTS; 0 if <2 games).
    ``closeout=True`` adds ``rel_closeout_PTS`` (closeout PTS − mean other-game PTS;
    0 if the player missed the closeout or has no other games).
    """
    paths = list_winner_csvs(winner_dir)
    if require_advanced or advanced:
        available = {p.name for p in Path(advanced_dir).glob("*_nba_finals_*.csv")}
        if require_advanced:
            paths = [p for p in paths if p.name in available]
    frames = [
        top_table_from_csv(
            p,
            top=top,
            rank=rank,
            advanced=advanced,
            advanced_dir=advanced_dir,
            advanced_cols=advanced_cols,
            q4=q4,
            wl=wl,
            pts_cv=pts_cv,
            closeout=closeout,
        )
        for p in paths
    ]
    return pd.concat(frames, axis=0).reset_index(drop=True)


def baseline_pick(df: pd.DataFrame, method: str = "pra") -> str:
    """Pick a Finals MVP guess from a cleaned champion box score."""
    work = df.copy()
    if method == "pts":
        idx = work["PTS"].idxmax()
    elif method == "pra":
        work["_score"] = work["PTS"] + work["TRB"] + work["AST"]
        idx = work["_score"].idxmax()
    else:
        raise ValueError(f"Unknown baseline method: {method}")
    return work.loc[idx, "Player"]


def control_trial(method: str = "pra", winner_dir: str = SERIES_TABLES_WINNER_DIR) -> pd.DataFrame:
    """Run a heuristic MVP pick for every Finals year; compare to actual MVP."""
    rows = []
    for path in list_winner_csvs(winner_dir):
        year = year_from_series_csv(path)
        cleaned = clean_boxscore(load_winner_csv(path), year)
        guess = baseline_pick(cleaned, method=method)
        actual = mvp_from_year(year)
        rows.append(
            {
                "Year": year,
                "Team": champ_from_year(year),
                "MVP": actual,
                "Guess": guess,
                "Correct": guess == actual or _norm_name(guess) == _norm_name(actual),
            }
        )
    return pd.DataFrame(rows)
