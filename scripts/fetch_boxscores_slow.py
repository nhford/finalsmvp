"""Fetch missing Finals game boxscores at 1 game / SLEEP_SEC (BRef-friendly).

Writes progress to output/boxscore_slow_fetch.log (same style as
headshot_slow_fetch.log). When the cache is complete, runs extract_wl_efg.py.

Usage:
  python3 scripts/fetch_boxscores_slow.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.paths import (  # noqa: E402
    BASE_URL,
    SERIES_HTML_BOXSCORES_DIR,
    SERIES_HTML_FINALS_DIR,
)
from helpers.q4 import game_links_from_series_html, parse_box_game_id  # noqa: E402

LOG = ROOT / "output" / "boxscore_slow_fetch.log"
CACHE = ROOT / SERIES_HTML_BOXSCORES_DIR
FINALS = ROOT / SERIES_HTML_FINALS_DIR
SLEEP_SEC = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; finalsmvp-research/1.0; +https://github.com/)",
}


def log(msg: str) -> None:
    line = f"{datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def missing_ids() -> list[str]:
    need: list[str] = []
    if not FINALS.exists():
        return need
    for p in sorted(FINALS.glob("*_nba_finals_*.html")):
        for href in game_links_from_series_html(p.read_text(encoding="utf-8")):
            gid = parse_box_game_id(href)
            if gid and not (CACHE / f"{gid}.html").exists():
                need.append(gid)
    return need


def fetch_one(gid: str) -> bool:
    path = CACHE / f"{gid}.html"
    url = f"{BASE_URL}/boxscores/{gid}.html"
    for attempt in range(6):
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code == 429:
            wait = 120 * (attempt + 1)
            log(f"  FAIL 429 — sleeping {wait}s (attempt {attempt + 1}/6)")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            log(f"  FAIL HTTP {r.status_code}")
            return False
        path.write_text(r.content.decode("utf-8", errors="replace"), encoding="utf-8")
        log(f"  saved {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
        return True
    log("  FAIL gave up after retries")
    return False


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    missing = missing_ids()
    log(f"Starting slow fetch: {len(missing)} games, {SLEEP_SEC}s between each")
    if not missing:
        log("Nothing to fetch.")
        return 0

    for i, gid in enumerate(missing, 1):
        log(f"[{i}/{len(missing)}] {gid}")
        ok = fetch_one(gid)
        if not ok:
            log("Stopping on failure; re-run to resume.")
            return 1
        if i < len(missing):
            log(f"  sleeping {SLEEP_SEC}s")
            time.sleep(SLEEP_SEC)

    left = missing_ids()
    log(f"Done. still missing: {len(left)}")
    for gid in left:
        log(f"  {gid}")

    if left:
        return 1

    log("Running extract_wl_efg.py")
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "extract_wl_efg.py")], cwd=ROOT)
    log("extract_wl_efg.py finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
