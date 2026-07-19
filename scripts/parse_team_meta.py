"""Parse Basketball-Reference team #meta HTML into tabular CSVs.

Writes:
  data/teams/champions_seasons.csv       — one row per champion season
  data/teams/champions_playoff_rounds.csv — one row per playoff series
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.naming import parse_team_html_stem

HTML_DIR = ROOT / "data" / "teams" / "html"
OUT_SEASONS = ROOT / "data" / "teams" / "champions_seasons.csv"
OUT_PLAYOFFS = ROOT / "data" / "teams" / "champions_playoff_rounds.csv"

RANK_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*(?:\(([^)]+)\))?\s*$"
)
RECORD_RE = re.compile(
    r"(?P<wins>\d+)-(?P<losses>\d+),\s*Finished\s+(?P<finish>.+?)\s+in\s+NBA\s+(?P<group>.+)",
    re.I,
)
COACH_RE = re.compile(r"([^,(]+?)\s*\((\d+)-(\d+)\)")
SERIES_RE = re.compile(
    r"(?P<result>Won|Lost)\s+(?P<round>.+?)\s+\((?P<w>\d+)-(?P<l>\d+)\)\s+versus\s+(?P<opponent>.+)",
    re.I,
)
SERIES_STATS_RE = re.compile(r"\s*\(\s*Series Stats\s*\)\s*$", re.I)


def clean_value(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split()).lstrip(":").strip()


def parse_value_rank(text: str) -> tuple[float | None, str | None]:
    text = clean_value(text)
    m = RANK_RE.match(text)
    if not m:
        return None, None
    return float(m.group(1)), (m.group(2) or None)


def strong_map(summary) -> dict[str, str]:
    """Map normalized label -> following text within each <p>."""
    out: dict[str, str] = {}
    for p in summary.find_all("p"):
        strongs = p.find_all("strong")
        if not strongs:
            continue
        # Clone-ish: walk strong tags and take text until next strong
        for strong in strongs:
            label = strong.get_text(" ", strip=True).rstrip(":").strip()
            label = re.sub(r"\s+", " ", label)
            chunks: list[str] = []
            for sib in strong.next_siblings:
                if getattr(sib, "name", None) == "strong":
                    break
                if getattr(sib, "name", None) == "br":
                    break
                if getattr(sib, "name", None) is None:
                    chunks.append(str(sib))
                else:
                    chunks.append(" " + sib.get_text(" ", strip=True) + " ")
            value = clean_value("".join(chunks))
            out[label] = value
    return out


def parse_coaches(coach_text: str) -> tuple[str, str | None, int | None, int | None]:
    """Return (coaches_display, primary_coach, primary_wins, primary_losses)."""
    coaches = COACH_RE.findall(coach_text)
    if not coaches:
        name = coach_text.strip() or None
        return coach_text.strip(), name, None, None
    display = "; ".join(f"{n.strip()} ({w}-{l})" for n, w, l in coaches)
    # Primary = coach with most wins that season
    primary = max(coaches, key=lambda c: int(c[1]))
    return display, primary[0].strip(), int(primary[1]), int(primary[2])


def parse_playoffs(summary) -> list[dict]:
    rounds = []
    for p in summary.find_all("p"):
        if "Playoffs" not in p.get_text():
            continue
        # Each series is typically separated by <br/>
        # Get text nodes after the Playoffs strong
        parts = []
        for br in p.find_all("br"):
            # text after this br until next br
            bits = []
            for sib in br.next_siblings:
                if getattr(sib, "name", None) == "br":
                    break
                bits.append(sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib))
            text = " ".join(" ".join(bits).split())
            if text:
                parts.append(text)
        # Fallback: split whole paragraph lines
        if not parts:
            parts = [ln.strip() for ln in p.get_text("\n").splitlines() if "versus" in ln]

        for i, text in enumerate(parts, start=1):
            text = SERIES_STATS_RE.sub("", clean_value(text))
            m = SERIES_RE.match(text)
            if not m:
                continue
            opponent = SERIES_STATS_RE.sub("", m.group("opponent").strip()).strip()
            rounds.append(
                {
                    "round_order": i,
                    "result": m.group("result").title(),
                    "round": m.group("round").strip(),
                    "wins": int(m.group("w")),
                    "losses": int(m.group("l")),
                    "opponent": opponent,
                    "series_text": text,
                }
            )
    return rounds


def parse_team_html(path: Path) -> tuple[dict, list[dict]]:
    abbrev, year = parse_team_html_stem(path.stem)  # BOS_2024 or legacy BOS2024

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    summary = soup.select_one('[data-template="Partials/Teams/Summary"]') or soup
    fields = strong_map(summary)

    h1_spans = summary.select("h1 span") if summary else []
    season = h1_spans[0].get_text(strip=True) if len(h1_spans) > 0 else None
    team = h1_spans[1].get_text(strip=True) if len(h1_spans) > 1 else None

    logo = soup.select_one("img.teamlogo")
    logo_url = logo["src"] if logo and logo.has_attr("src") else None

    record_raw = fields.get("Record", "")
    rm = RECORD_RE.search(record_raw)
    wins = int(rm.group("wins")) if rm else None
    losses = int(rm.group("losses")) if rm else None
    finish = rm.group("finish").strip() if rm else None
    group = " ".join(rm.group("group").split()) if rm else None

    coaches_display, primary_coach, primary_w, primary_l = parse_coaches(
        fields.get("Coach", "")
    )

    pts_g, pts_g_rank = parse_value_rank(fields.get("PTS/G", ""))
    opp_pts_g, opp_pts_g_rank = parse_value_rank(fields.get("Opp PTS/G", ""))
    srs, srs_rank = parse_value_rank(fields.get("SRS", ""))
    pace, pace_rank = parse_value_rank(fields.get("Pace", ""))
    ortg, ortg_rank = parse_value_rank(fields.get("Off Rtg", ""))
    drtg, drtg_rank = parse_value_rank(fields.get("Def Rtg", ""))
    net_rtg, net_rtg_rank = parse_value_rank(fields.get("Net Rtg", ""))
    # Expected W-L is "66-16 (1st of 30)" — not a single numeric value
    exp_raw = clean_value(fields.get("Expected W-L", ""))
    exp_m = re.match(r"\s*(\d+)-(\d+)\s*(?:\(([^)]+)\))?", exp_raw)
    exp_wins = int(exp_m.group(1)) if exp_m else None
    exp_losses = int(exp_m.group(2)) if exp_m else None
    exp_rank = exp_m.group(3) if exp_m else None

    attendance_raw = clean_value(fields.get("Attendance", ""))
    att_m = re.match(r"([\d,]+)\s*(?:\(([^)]+)\))?", attendance_raw)
    attendance = int(att_m.group(1).replace(",", "")) if att_m else None
    attendance_rank = att_m.group(2) if att_m else None

    odds = clean_value(fields.get("Preseason Odds", ""))
    champ_odds = None
    over_under = None
    if odds:
        cm = re.search(r"Championship\s+([+\-]\d+|\d+)", odds, re.I)
        om = re.search(r"Over-Under\s+([\d.]+)", odds, re.I)
        champ_odds = cm.group(1) if cm else None
        over_under = float(om.group(1)) if om else None

    playoff_rounds = parse_playoffs(summary)
    for r in playoff_rounds:
        r["year"] = year
        r["abbrev"] = abbrev
        r["team"] = team

    finals_opponent = None
    for r in playoff_rounds:
        if "Finals" in r["round"] and "Conference" not in r["round"]:
            finals_opponent = r["opponent"]

    row = {
        "year": year,
        "season": season,
        "abbrev": abbrev,
        "team": team,
        "wins": wins,
        "losses": losses,
        "finish": finish,
        "conference_or_division": group,
        "coach": coaches_display,
        "primary_coach": primary_coach,
        "primary_coach_wins": primary_w,
        "primary_coach_losses": primary_l,
        "executive": fields.get("Executive") or None,
        "pts_g": pts_g,
        "pts_g_rank": pts_g_rank,
        "opp_pts_g": opp_pts_g,
        "opp_pts_g_rank": opp_pts_g_rank,
        "srs": srs,
        "srs_rank": srs_rank,
        "pace": pace,
        "pace_rank": pace_rank,
        "off_rtg": ortg,
        "off_rtg_rank": ortg_rank,
        "def_rtg": drtg,
        "def_rtg_rank": drtg_rank,
        "net_rtg": net_rtg,
        "net_rtg_rank": net_rtg_rank,
        "expected_wins": exp_wins,
        "expected_losses": exp_losses,
        "expected_wl_rank": exp_rank,
        "championship_odds": champ_odds,
        "over_under": over_under,
        "arena": fields.get("Arena") or None,
        "attendance": attendance,
        "attendance_rank": attendance_rank,
        "finals_opponent": finals_opponent,
        "playoff_path": " | ".join(r["series_text"] for r in playoff_rounds) or None,
        "logo_url": logo_url,
        "source_html": str(path.relative_to(ROOT)) if path.is_absolute() else str(path),
    }
    return row, playoff_rounds


def main() -> None:
    season_rows = []
    playoff_rows = []
    for path in sorted(HTML_DIR.glob("*.html")):
        row, rounds = parse_team_html(path)
        season_rows.append(row)
        playoff_rows.extend(rounds)

    seasons = pd.DataFrame(season_rows).sort_values("year", ascending=False)
    # Keep odds as strings so "+450" is preserved
    if "championship_odds" in seasons.columns:
        seasons["championship_odds"] = seasons["championship_odds"].astype("string")

    playoffs = pd.DataFrame(playoff_rows)
    if not playoffs.empty:
        playoffs = playoffs.sort_values(["year", "round_order"], ascending=[False, True])
        cols = [
            "year",
            "abbrev",
            "team",
            "round_order",
            "result",
            "round",
            "wins",
            "losses",
            "opponent",
            "series_text",
        ]
        playoffs = playoffs[cols]

    OUT_SEASONS.parent.mkdir(parents=True, exist_ok=True)
    seasons.to_csv(OUT_SEASONS, index=False)
    playoffs.to_csv(OUT_PLAYOFFS, index=False)
    print(f"Wrote {len(seasons)} seasons -> {OUT_SEASONS}")
    print(f"Wrote {len(playoffs)} playoff rounds -> {OUT_PLAYOFFS}")


if __name__ == "__main__":
    main()
