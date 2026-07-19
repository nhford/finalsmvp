"""HTTP/HTML fetch helpers with local cache."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Callable

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import TimeoutError as PlaywrightTimeout
    from playwright.async_api import async_playwright
except ImportError:  # optional; only needed for save_path_html / get_html
    PlaywrightTimeout = Exception
    async_playwright = None


def name(url: str) -> str:
    """Default cache filename from a URL leaf (hyphens → underscores)."""
    from helpers.naming import bbr_slug_to_stem, finals_html_name, team_html_name_from_url

    leaf = url.rstrip("/").split("/")[-1]
    # Team season pages: /teams/BOS/2024.html
    if "/teams/" in url and leaf.endswith(".html"):
        return team_html_name_from_url(url)
    # Finals series pages
    if "nba-finals" in url or "nba_finals" in leaf:
        return finals_html_name(url)
    return f"{bbr_slug_to_stem(url)}.html" if leaf.endswith(".html") else bbr_slug_to_stem(url)


def name_csv(url: str) -> str:
    from helpers.naming import finals_csv_name

    if "nba-finals" in url or "nba_finals" in url:
        return finals_csv_name(url)
    return name(url).replace(".html", ".csv").replace("html", "csv")


def save(
    link: str,
    directory: str,
    sleep: int = 10,
    name_fn: Callable[[str], str] = name,
) -> str:
    save_path = os.path.join(directory, name_fn(link))
    if not os.path.exists(save_path):
        time.sleep(sleep)
        response = requests.get(link)
        text = response.text
        with open(save_path, "w+") as f:
            f.write(text)
    else:
        with open(save_path, "r") as f:
            text = f.read()
    return text


def save_tag(
    link: str,
    directory: str,
    tag: str,
    sleep: int = 10,
    name_fn: Callable[[str], str] = name,
) -> str:
    save_path = os.path.join(directory, name_fn(link))
    if not os.path.exists(save_path):
        response = requests.get(link)
        text = response.text
        bs = BeautifulSoup(text, "html.parser")
        text = bs.find(id=tag)
        time.sleep(sleep)
        with open(save_path, "w+") as f:
            f.write(str(text))
    else:
        with open(save_path, "r") as f:
            text = f.read()
    return text


async def get_html(url: str, selector: str, sleep: int = 5, retries: int = 3) -> str:
    """Fetch rendered HTML for a CSS selector via Playwright."""
    if async_playwright is None:
        raise ImportError("playwright is required for get_html; pip install playwright")
    for i in range(1, retries + 1):
        time.sleep(sleep * i)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(url)
                html = await page.inner_html(selector)
                await browser.close()
                return html
        except PlaywrightTimeout:
            if i == retries:
                raise
    return ""


async def save_path_html(
    link: str,
    directory: str,
    name_fn: Callable[[str], str],
    tag: str,
) -> str:
    """Cache Playwright-rendered HTML for a page fragment."""
    save_path = os.path.join(directory, name_fn(link))
    if not os.path.exists(save_path):
        html = await get_html(link, tag)
        with open(save_path, "w+") as f:
            f.write(html)
    else:
        with open(save_path, "r") as f:
            html = f.read()
    return html


# Back-compat alias used in older notebook cells.
savePath = save_path_html


def run_async(coro):
    """Run an async helper from a sync notebook cell."""
    return asyncio.get_event_loop().run_until_complete(coro)
