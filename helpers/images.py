"""Local logo / image cache helpers."""

from __future__ import annotations

import os
from io import BytesIO

import requests
from PIL import Image

from helpers.paths import LOGOS_DIR
from helpers.scrape import name


def name_img(url: str, logos_dir: str = LOGOS_DIR) -> str:
    return os.path.join(logos_dir, name(url))


def fetch_image(url: str, local_path: str):
    try:
        if os.path.exists(local_path):
            return Image.open(local_path)

        response = requests.get(url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        image.save(local_path)
        return image
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the image: {e}")
        return None
    except OSError as e:
        print(f"Error opening the image: {e}")
        return None
