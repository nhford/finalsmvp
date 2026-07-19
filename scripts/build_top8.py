"""Rebuild output/full_top_8*.csv and data/meta/finals_series_games.csv."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.boxscores import build_finals_series_games, build_top8
from helpers.paths import (
    FINALS_SERIES_GAMES_CSV,
    FULL_TOP_8_CSV,
    FULL_TOP_8_UNRANKED_ADVANCED_CSV,
    FULL_TOP_8_UNRANKED_CSV,
    META_DIR,
    OUTPUT_DIR,
)


def main() -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(META_DIR).mkdir(parents=True, exist_ok=True)

    series_games = build_finals_series_games()
    series_games.to_csv(FINALS_SERIES_GAMES_CSV, index=False)
    print(
        f"Wrote {FINALS_SERIES_GAMES_CSV} "
        f"({len(series_games)} years, games {series_games.Games.min()}–{series_games.Games.max()})"
    )

    ranked = build_top8(rank=True)
    unranked = build_top8(rank=False)
    unranked_adv = build_top8(rank=False, advanced=True, require_advanced=True)

    ranked.to_csv(FULL_TOP_8_CSV)
    unranked.to_csv(FULL_TOP_8_UNRANKED_CSV)
    unranked_adv.to_csv(FULL_TOP_8_UNRANKED_ADVANCED_CSV)
    print(
        f"Wrote {FULL_TOP_8_CSV} and {FULL_TOP_8_UNRANKED_CSV} "
        f"({ranked.Year.nunique()} years, {len(ranked)} rows)"
    )
    print(
        f"Wrote {FULL_TOP_8_UNRANKED_ADVANCED_CSV} "
        f"({unranked_adv.Year.nunique()} years with USG%/ORtg/DRtg, {len(unranked_adv)} rows)"
    )


if __name__ == "__main__":
    main()
