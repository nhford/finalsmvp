"""Build web/src/data/finals.json from ML + advanced + season meta CSVs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.paths import (
    CHAMPIONS_SEASONS_CSV,
    FEATURE_WEIGHTS_JSON,
    FRONTEND_FINALS_JSON,
    FULL_TOP_8_UNRANKED_ADVANCED_CSV,
    OUTPUT_DIR,
)

ML_OUTPUT_CSV = f"{OUTPUT_DIR}/machine_learning_output.csv"
FRONTEND_JSON = ROOT / "web" / "src" / "data" / "finals.json"
OUTPUT_JSON = ROOT / FRONTEND_FINALS_JSON

STAT_COLS = [
    "G",
    "GM",
    "Series_G",
    "MP",
    "PTS",
    "TRB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "FG%",
    "3P%",
    "USG%",
    "NetRtg",
    "ORtg",
    "DRtg",
]


def fix_mojibake(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes"}


def num(value: object, digits: int | None = None) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if digits is None:
        return number
    return round(number, digits)


def candidate_stats(stats_row: pd.Series | None) -> dict:
    if stats_row is None:
        return {col: None for col in STAT_COLS}

    out: dict = {}
    for col in STAT_COLS:
        if col not in stats_row.index:
            out[col] = None
            continue
        raw = num(stats_row[col])
        if raw is None:
            out[col] = None
        elif col in {"G", "GM", "Series_G", "MP", "PTS", "TRB", "AST", "STL", "BLK", "TOV"}:
            out[col] = int(raw) if float(raw).is_integer() else round(raw, 1)
        elif "%" in col:
            out[col] = round(raw, 3)
        else:
            out[col] = round(raw, 1)

    if out.get("NetRtg") is None and out.get("ORtg") is not None and out.get("DRtg") is not None:
        out["NetRtg"] = round(float(out["ORtg"]) - float(out["DRtg"]), 1)
    return out


def main() -> None:
    ml = pd.read_csv(ROOT / ML_OUTPUT_CSV)
    advanced = pd.read_csv(ROOT / FULL_TOP_8_UNRANKED_ADVANCED_CSV)
    seasons = pd.read_csv(ROOT / CHAMPIONS_SEASONS_CSV)

    for frame in (ml, advanced):
        if "Player" in frame.columns:
            frame["Player"] = frame["Player"].map(fix_mojibake)
    if "MVP" in ml.columns:
        ml["MVP"] = ml["MVP"].map(fix_mojibake)

    # Drop unnamed index column from advanced export if present
    advanced = advanced.loc[:, ~advanced.columns.str.match(r"^Unnamed")]

    seasons_by_year = seasons.set_index("year")
    years: list[dict] = []

    for year, group in ml.groupby("Year", sort=False):
        year = int(year)
        group = group.sort_values(["Rank", "mvp_share"], ascending=[True, False])
        predicted = group.loc[group["mvp_share"].idxmax()]
        actual_rows = group[group["mvp"].map(as_bool)]
        if actual_rows.empty:
            raise SystemExit(f"No actual MVP row for {year}")
        actual = actual_rows.iloc[0]

        season = seasons_by_year.loc[year] if year in seasons_by_year.index else None
        team = str(predicted["Team"])
        abbrev = str(season["abbrev"]) if season is not None else ""
        logo_url = str(season["logo_url"]) if season is not None else ""
        opponent = str(season["finals_opponent"]) if season is not None else ""

        year_stats = advanced[advanced["Year"] == year].set_index("Player")

        candidates: list[dict] = []
        for _, row in group.iterrows():
            player = str(row["Player"])
            stats_row = year_stats.loc[player] if player in year_stats.index else None
            if stats_row is not None and isinstance(stats_row, pd.DataFrame):
                stats_row = stats_row.iloc[0]
            candidates.append(
                {
                    "player": player,
                    "mvpShare": num(row["mvp_share"], 3),
                    "probMvp": num(row["prob_mvp"], 3),
                    "rank": int(row["Rank"]),
                    "isActualMvp": as_bool(row["mvp"]),
                    "isPredicted": player == str(predicted["Player"]),
                    "stats": candidate_stats(stats_row),
                }
            )

        predicted_player = str(predicted["Player"])
        actual_player = str(actual["Player"])
        years.append(
            {
                "year": year,
                "team": team,
                "teamAbbr": abbrev,
                "logoUrl": logo_url,
                "opponent": opponent,
                "predictedPlayer": predicted_player,
                "predictedShare": num(predicted["mvp_share"], 3),
                "actualPlayer": actual_player,
                "actualShare": num(actual["mvp_share"], 3),
                "correct": predicted_player == actual_player,
                "candidates": candidates,
            }
        )

    years.sort(key=lambda row: row["year"], reverse=True)

    weights_path = ROOT / FEATURE_WEIGHTS_JSON
    if weights_path.exists():
        weights_payload = json.loads(weights_path.read_text(encoding="utf-8"))
        feature_weights = weights_payload.get("features", [])
        feature_vif = weights_payload.get("vif", [])
        feature_top_pairs = weights_payload.get("topPairs", [])
        feature_n = weights_payload.get("n")
    else:
        feature_weights = []
        feature_vif = []
        feature_top_pairs = []
        feature_n = None

    teams = sorted({row["teamAbbr"] for row in years if row["teamAbbr"]})
    payload = {
        "generatedFrom": ML_OUTPUT_CSV,
        "minYear": min(row["year"] for row in years),
        "maxYear": max(row["year"] for row in years),
        "teams": teams,
        "featureWeights": feature_weights,
        "featureVif": feature_vif,
        "featureTopPairs": feature_top_pairs,
        "featureN": feature_n,
        "years": years,
    }

    FRONTEND_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    FRONTEND_JSON.write_text(text, encoding="utf-8")
    OUTPUT_JSON.write_text(text, encoding="utf-8")

    correct = sum(1 for row in years if row["correct"])
    print(
        f"Wrote {FRONTEND_JSON.relative_to(ROOT)} and "
        f"{OUTPUT_JSON.relative_to(ROOT)} "
        f"({len(years)} years, {correct}/{len(years)} correct picks)"
    )


if __name__ == "__main__":
    main()
