"""Fetch missing Finals top-8 headshots at 1 player/minute (BRef-friendly)."""

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
LOG = ROOT / "output" / "headshot_slow_fetch.log"
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
SLEEP_SEC = 20

# Prefer known IDs so we only need the image request when possible.
KNOWN_IDS = {
    "Aaron Gordon": "gordoaa01",
    "Alonzo Mourning": "mournal01",
    "Andrew Bynum": "bynuman01",
    "Andrew Wiggins": "wiggian01",
    "Anthony Davis": "davisan02",
    "Antoine Walker": "walkean01",
    "Beno Udrih": "udrihbe01",
    "Bobby Portis": "portibo01",
    "Boris Diaw": "diawbo01",
    "Brook Lopez": "lopezbr01",
    "Bruce Brown": "brownbr01",
    "Bryn Forbes": "forbebr01",
    "Carl Herrera": "herreca01",
    "Charles Jones": "jonesch02",
    "Chris Andersen": "anderch01",
    "Chris Bosh": "boshch01",
    "Christian Braun": "braunch01",
    "Chucky Brown": "brownch01",
    "Danny Green": "greenda02",
    "David West": "westda01",
    "DeShawn Stevenson": "stevede01",
    "Dirk Nowitzki": "nowitdi01",
    "Dwyane Wade": "wadedw01",
    "Eddie House": "houseed01",
    "Fred VanVleet": "vanvlfr01",
    "Gary Payton": "paytoga01",
    "Gary Payton II": "paytoga02",
    "Giannis Antetokounmpo": "antetgi01",
    "Ian Clark": "clarkia01",
    "Ian Mahinmi": "mahinia01",
    "J.J. Barea": "bareajo01",
    "JaVale McGee": "mcgeeja01",
    "Jamal Murray": "murraja01",
    "James Posey": "poseyja01",
    "Jaren Jackson": "jacksja01",
    "Jason Kidd": "kiddja01",
    "Jason Terry": "terryja01",
    "Jason Williams": "willija02",
    "Jeff Green": "greenje02",
    "Jordan Bell": "belljo01",
    "Jordan Farmar": "farmajo01",
    "Jordan Poole": "poolejo01",
    "Kawhi Leonard": "leonaka01",
    "Kentavious Caldwell-Pope": "caldwke01",
    "Kevin Durant": "duranke01",
    "Kevin Garnett": "garneke01",
    "Kevon Looney": "looneke01",
    "Khris Middleton": "middlkh01",
    "Kristaps Porzingis": "porzikr01",
    "Kyle Kuzma": "kuzmaky01",
    "Kyle Lowry": "lowryky01",
    "Lamar Odom": "odomla01",
    "Leon Powe": "powele01",
    "Luke Walton": "waltolu01",
    "Manu Ginóbili": "ginobma01",
    "Marc Gasol": "gasolma01",
    "Mario Chalmers": "chalmma01",
    "Markieff Morris": "morrima02",
    "Metta World Peace": "artesro01",
    "Michael Porter Jr.": "portemi01",
    "Mike Miller": "millemi01",
    "Nazr Mohammed": "mohamna01",
    "Nikola Jokic": "jokicni01",
    "Norman Powell": "powelno01",
    "Norris Cole": "coleno01",
    "Otto Porter Jr.": "porteot01",
    "P.J. Brown": "brownpj01",
    "P.J. Tucker": "tuckepj01",
    "Pascal Siakam": "siakapa01",
    "Pat Connaughton": "connapa01",
    "Patty Mills": "millspa02",
    "Pau Gasol": "gasolpa01",
    "Paul Pierce": "piercpa01",
    "Rajon Rondo": "rondora01",
    "Ray Allen": "allenra02",
    "Scott Williams": "willisc01",
    "Serge Ibaka": "ibakase01",
    "Shane Battier": "battish01",
    "Shannon Brown": "brownsh01",
    "Shawn Marion": "mariosh01",
    "Tiago Splitter": "splitti01",
    "Toni Kukoč": "kukocto01",
    "Tony Campbell": "campbto01",
    "Trevor Ariza": "arizatr01",
    "Tyson Chandler": "chandty01",
    "Udonis Haslem": "hasleud01",
}


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


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


def get(url: str) -> requests.Response:
    while True:
        r = requests.get(url, headers=HEADERS, timeout=45)
        if r.status_code != 429:
            return r
        log("429 — sleeping 3 minutes before retry")
        time.sleep(180)


def search_pid(name: str) -> str | None:
    url = (
        "https://www.basketball-reference.com/search/search.fcgi?"
        f"search={quote(name)}"
    )
    r = get(url)
    if r.status_code != 200:
        return None
    if "/players/" in r.url and r.url.endswith(".html"):
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", r.url)
        return m.group(1) if m else None
    soup = BeautifulSoup(r.text, "html.parser")
    target = norm(name)
    for a in soup.select("a[href*='/players/']"):
        href = a.get("href") or ""
        m = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", href)
        if m and norm(a.get_text(strip=True)) == target:
            return m.group(1)
    return None


def write_manifest(data: dict) -> None:
    slugs = sorted(
        {
            slugify(c["player"])
            for row in data["years"]
            for c in row["candidates"]
            if (OUT_DIR / f"{slugify(c['player'])}.png").exists()
        }
    )
    MANIFEST.write_text(json.dumps(slugs, indent=2) + "\n")


def fetch_one(name: str, pid: str, slug: str) -> bool:
    out = OUT_DIR / f"{slug}.png"
    if out.exists() and out.stat().st_size > 1000:
        return True
    url = HEADSHOT.format(pid=pid)
    resp = get(url)
    if resp.status_code != 200 or not resp.content.startswith(b"\xff\xd8"):
        log(f"  FAIL image {resp.status_code} pid={pid}")
        return False
    raw = Image.open(BytesIO(resp.content)).convert("RGBA")
    cut = remove(raw)
    cut.save(out, "PNG")
    log(f"  saved {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
    return True


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for src_name, dest_name in {
        "manu_gin_bili.png": "manu_ginobili.png",
        "toni_kuko.png": "toni_kukoc.png",
    }.items():
        src, dest = OUT_DIR / src_name, OUT_DIR / dest_name
        if src.exists() and not dest.exists():
            src.rename(dest)
            log(f"renamed {src_name} -> {dest_name}")

    data = json.loads(FINALS_JSON.read_text())
    have = {p.stem for p in OUT_DIR.glob("*.png")}
    missing = sorted(
        {
            c["player"]
            for row in data["years"]
            for c in row["candidates"]
            if slugify(c["player"]) not in have
        }
    )
    log(f"Starting slow fetch: {len(missing)} players, {SLEEP_SEC}s between each")

    for i, name in enumerate(missing, 1):
        slug = slugify(name)
        log(f"[{i}/{len(missing)}] {name}")
        pid = KNOWN_IDS.get(name)
        if not pid:
            log("  searching BRef for id…")
            pid = search_pid(name)
            # count search as the minute's request; wait before image
            if i < len(missing) or True:
                time.sleep(SLEEP_SEC)
        if not pid:
            log("  unresolved — skip")
            time.sleep(SLEEP_SEC)
            continue
        ok = fetch_one(name, pid, slug)
        if ok:
            write_manifest(data)
        if i < len(missing):
            log(f"  sleeping {SLEEP_SEC}s")
            time.sleep(SLEEP_SEC)

    write_manifest(data)
    have = {p.stem for p in OUT_DIR.glob("*.png")}
    left = sorted(
        {
            c["player"]
            for row in data["years"]
            for c in row["candidates"]
            if slugify(c["player"]) not in have
        }
    )
    log(f"Done. still missing: {len(left)}")
    for p in left:
        log(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
