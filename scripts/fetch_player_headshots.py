"""Download BRef headshots for Finals top-8 candidates and remove backgrounds."""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from PIL import Image
from rembg import remove

ROOT = Path(__file__).resolve().parents[1]
FINALS_JSON = ROOT / "web" / "src" / "data" / "finals.json"
OUT_DIR = ROOT / "web" / "public" / "images" / "players"
MANIFEST = ROOT / "web" / "src" / "data" / "playerImages.json"
HEADSHOT = (
    "https://www.basketball-reference.com/req/202106291/images/headshots/{pid}.jpg"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.basketball-reference.com/",
}

# Known slug repairs from earlier accent-stripping runs
RENAME = {
    "manu_gin_bili.png": "manu_ginobili.png",
    "toni_kuko.png": "toni_kukoc.png",
}


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace(".", "")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def get(url: str, *, retries: int = 6) -> requests.Response:
    last: requests.Response | None = None
    for attempt in range(retries):
        last = requests.get(url, headers=HEADERS, timeout=45)
        if last.status_code != 429:
            return last
        wait = 15 * (attempt + 1)
        print(f"  429 on {url} — sleep {wait}s", flush=True)
        time.sleep(wait)
    assert last is not None
    return last


def fetch_roster(team: str, year: int) -> dict[str, str]:
    url = f"https://www.basketball-reference.com/teams/{team}/{year}.html"
    r = get(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    mapping: dict[str, str] = {}
    for a in soup.select("#roster a[href*='/players/']"):
        href = a.get("href") or ""
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", href)
        if not m:
            continue
        mapping[a.get_text(strip=True)] = m.group(1)
    return mapping


def search_pid(name: str) -> str | None:
    url = (
        "https://www.basketball-reference.com/search/search.fcgi?"
        f"search={quote(name)}"
    )
    r = get(url)
    if r.status_code != 200:
        return None
    # Direct player page redirect
    if "/players/" in r.url and r.url.endswith(".html"):
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", r.url)
        return m.group(1) if m else None
    soup = BeautifulSoup(r.text, "html.parser")
    target = norm(name)
    for a in soup.select("div.search-item-name a[href*='/players/']"):
        href = a.get("href") or ""
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", href)
        if not m:
            continue
        if norm(a.get_text(strip=True)) == target:
            return m.group(1)
    # first players hit as weak fallback
    for a in soup.select("a[href*='/players/']"):
        href = a.get("href") or ""
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", href)
        if m and norm(a.get_text(strip=True)) == target:
            return m.group(1)
    return None


def resolve_pid(name: str, roster: dict[str, str]) -> str | None:
    if name in roster:
        return roster[name]
    key = norm(name)
    for n, pid in roster.items():
        if norm(n) == key:
            return pid
    return None


def download_cutout(pid: str, slug: str) -> bool:
    out = OUT_DIR / f"{slug}.png"
    if out.exists() and out.stat().st_size > 1000:
        return True
    url = HEADSHOT.format(pid=pid)
    resp = get(url)
    if resp.status_code != 200 or not resp.content.startswith(b"\xff\xd8"):
        print(f"  download FAIL {resp.status_code} {pid}")
        return False
    raw = Image.open(BytesIO(resp.content)).convert("RGBA")
    cut = remove(raw)
    cut.save(out, "PNG")
    print(f"  -> {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
    return True


def main() -> None:
    data = json.loads(FINALS_JSON.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for src_name, dest_name in RENAME.items():
        src = OUT_DIR / src_name
        dest = OUT_DIR / dest_name
        if src.exists() and not dest.exists():
            src.rename(dest)
            print(f"renamed {src_name} -> {dest_name}")

    nested = OUT_DIR / "nyk_2026"
    if nested.is_dir():
        for p in nested.glob("*.png"):
            dest = OUT_DIR / p.name
            if not dest.exists():
                dest.write_bytes(p.read_bytes())

    # Collect unique missing players, and year-teams still needing roster lookup
    have = {p.stem for p in OUT_DIR.glob("*.png")}
    missing_by_team: dict[tuple[int, str], list[str]] = {}
    for row in data["years"]:
        year, team = int(row["year"]), row["teamAbbr"]
        for c in row["candidates"]:
            player = c["player"]
            if slugify(player) in have:
                continue
            missing_by_team.setdefault((year, team), []).append(player)

    print(f"Teams with missing players: {len(missing_by_team)}")
    id_to_meta: dict[str, tuple[str, str]] = {}
    still_missing: list[str] = []

    for i, ((year, team), players) in enumerate(sorted(missing_by_team.items())):
        print(f"[{i + 1}/{len(missing_by_team)}] roster {team} {year}", flush=True)
        time.sleep(6)
        try:
            roster = fetch_roster(team, year)
        except Exception as exc:
            print(f"  roster FAIL: {exc}")
            roster = {}
        for player in players:
            slug = slugify(player)
            if slug in have:
                continue
            pid = resolve_pid(player, roster)
            if not pid:
                print(f"  search {player}", flush=True)
                time.sleep(3)
                pid = search_pid(player)
            if not pid:
                still_missing.append(player)
                print(f"  unresolved: {player}")
                continue
            id_to_meta[pid] = (player, slug)

    print(f"\nPlayers to fetch: {len(id_to_meta)}")
    ok = 0
    for i, (pid, (name, slug)) in enumerate(
        sorted(id_to_meta.items(), key=lambda x: x[1][1])
    ):
        print(f"[{i + 1}/{len(id_to_meta)}] {name} ({pid})", flush=True)
        time.sleep(1.2)
        if download_cutout(pid, slug):
            have.add(slug)
            ok += 1

    # Final manifest = every candidate slug that exists on disk
    all_slugs = sorted(
        {
            slugify(c["player"])
            for row in data["years"]
            for c in row["candidates"]
            if (OUT_DIR / f"{slugify(c['player'])}.png").exists()
        }
    )
    MANIFEST.write_text(json.dumps(all_slugs, indent=2) + "\n")
    print(f"\nFetched this run: {ok}")
    print(f"Manifest size: {len(all_slugs)} -> {MANIFEST.relative_to(ROOT)}")
    leftover = sorted(
        {
            c["player"]
            for row in data["years"]
            for c in row["candidates"]
            if slugify(c["player"]) not in all_slugs
        }
    )
    if leftover:
        print(f"Still missing ({len(leftover)}):")
        for p in leftover:
            print(f"  {p}")


if __name__ == "__main__":
    sys.exit(main())
