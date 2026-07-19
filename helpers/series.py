"""Basketball-Reference series / box-score helpers."""

from __future__ import annotations

import re

import pandas as pd
from bs4 import BeautifulSoup

from helpers.paths import BASE_URL, SERIES_HTML_DIR, SERIES_TABLES_WINNER_DIR
from helpers.scrape import save


def get_seed(string: str) -> int:
    return int(string[string.find("(") + 1 : string.find(")")])


def get_team(string: str) -> str:
    return string[: string.find("(")]


# Back-compat aliases
getSeed = get_seed
getTeam = get_team


def pbp(url: str, html_dir: str = SERIES_HTML_DIR, base: str = BASE_URL) -> list[str]:
    print(url)
    text = save(url, html_dir)
    bs = BeautifulSoup(text, "html.parser")
    summaries = bs.find(id="div_other_scores")
    boxes = [base + tag["href"] for tag in summaries.find_all("a") if "box" in tag["href"]]
    return [u.replace("boxscores", "boxscores/pbp") for u in boxes]


def get_img(
    url: str,
    home: bool = True,
    tables_dir: str = SERIES_TABLES_WINNER_DIR,
) -> str:
    text = save(url, tables_dir)
    bs = BeautifulSoup(text, "html.parser")
    summaries = bs.find(id="content")
    arr = summaries.find_all("img")
    return arr[1]["src"] if home else arr[0]["src"]


getImg = get_img


def get_score(
    url: str,
    game: int,
    winner: bool = True,
    html_dir: str = SERIES_HTML_DIR,
) -> int:
    class_ = "winner" if winner else "loser"
    text = save(url, html_dir)
    bs = BeautifulSoup(text, "html.parser")
    summaries = bs.find(id="div_other_scores")
    return int(summaries.find_all("tr", class_=class_)[game - 1].find("td", class_="right").text)


getScore = get_score


def series_sum(url: str, games: int, html_dir: str = SERIES_HTML_DIR) -> list[int]:
    w, l = 0, 0
    for i in range(games):
        w += get_score(url, i, True, html_dir=html_dir)
        l += get_score(url, i, False, html_dir=html_dir)
    return [w, l]


seriesSum = series_sum


def mov(url: str, games: int, html_dir: str = SERIES_HTML_DIR) -> float:
    w, l = series_sum(url, games, html_dir=html_dir)
    return round((w - l) / games, 2)


def home(url: str, team: str, html_dir: str = SERIES_HTML_DIR) -> bool:
    text = save(url, html_dir)
    bs = BeautifulSoup(text, "html.parser")
    tags = bs.h2.find_all("a")
    names = [tag.text for tag in tags]
    return team.strip() == names[1]


def stats_string(url: str, tables_dir: str = SERIES_TABLES_WINNER_DIR) -> str:
    text = save(url, tables_dir)
    bs = BeautifulSoup(text, "html.parser")
    stats = bs.find(id="all_game-summary")
    return str(stats)


statsString = stats_string


def ties(url: str, tables_dir: str = SERIES_TABLES_WINNER_DIR) -> int:
    string = stats_string(url, tables_dir=tables_dir)
    i = string.find("Ties<")
    chunk = string[i : string.find("</td>", i) + 1]
    return int(re.search(r">(\d+)<", chunk).group(1))


def leads(url: str, tables_dir: str = SERIES_TABLES_WINNER_DIR) -> int:
    string = stats_string(url, tables_dir=tables_dir)
    i = string.find("Lead changes<")
    chunk = string[i : string.find("</td>", i) + 1]
    return int(re.search(r">(\d+)<", chunk).group(1))


def convert_time(string: str) -> pd.Timedelta:
    parts = string.split(":")
    minutes = int(parts[0])
    seconds = float(parts[1])
    return pd.to_timedelta(minutes, unit="m") + pd.to_timedelta(seconds, unit="s")


convertTime = convert_time


def tied(
    url: str,
    convert: bool = True,
    tables_dir: str = SERIES_TABLES_WINNER_DIR,
):
    string = stats_string(url, tables_dir=tables_dir)
    i = string.find("Game tied")
    chunk = string[i : string.find("</td>", i) + 1]
    ret = re.search(r"\b\d+:\d+\.\d+\b", chunk).group(0)
    return convert_time(ret) if convert else ret


def away_led(
    url: str,
    convert: bool = True,
    tables_dir: str = SERIES_TABLES_WINNER_DIR,
):
    string = stats_string(url, tables_dir=tables_dir)
    i = string.find("led")
    chunk = string[i : string.find("</td>", i) + 1]
    ret = re.search(r"\b\d+:\d+\.\d+\b", chunk).group(0)
    return convert_time(ret) if convert else ret


awayLed = away_led


def home_led(
    url: str,
    convert: bool = True,
    tables_dir: str = SERIES_TABLES_WINNER_DIR,
):
    string = stats_string(url, tables_dir=tables_dir)
    j = string.find("led")
    i = string.find("led", j + 1)
    chunk = string[i : string.find("</td>", i) + 1]
    ret = re.search(r"\b\d+:\d+\.\d+\b", chunk).group(0)
    return convert_time(ret) if convert else ret


homeLed = home_led


def add_pbp(df: pd.DataFrame, game: int) -> pd.DataFrame:
    full = df.copy()
    col = f"g{game}"
    labels = [f"tie{game}", f"leads{game}", f"tied{game}", f"homeLed{game}", f"awayLed{game}"]
    funcs = [ties, leads, tied, home_led, away_led]
    for i, func in enumerate(funcs):
        full.insert(full.columns.get_loc(col) + i + 1, labels[i], full[col].apply(func))
    return full


addPBP = add_pbp


def series_name(string: str) -> str:
    dictionary = {
        "Eastern Conf First Round": "R1",
        "Western Conf First Round": "R1",
        "Eastern Conf Semifinals": "R2",
        "Western Conf Semifinals": "R2",
        "Eastern Conf Finals": "ECF",
        "Western Conf Finals": "WCF",
        "Finals": "Finals",
    }
    return dictionary[string]


seriesName = series_name
