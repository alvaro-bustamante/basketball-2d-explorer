"""Player photos and crests: download once, cache on disk, crop photos to the face.

Face detection uses OpenCV when it is installed (pip install opencv-python-headless);
otherwise a crop based on how team photos are usually framed (head in the
upper middle of the picture) is used.
"""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from pathlib import Path

import requests

CACHE_DIR = Path("data") / "cache" / "images"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; basketball-2d-explorer/1.0)"}


def load_image(url: str | None):
    """PIL image from a URL (PNG/JPG/WebP), cached in data/cache/images/. None if not possible."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    path = CACHE_DIR / (hashlib.md5(url.encode()).hexdigest() + ".bin")
    try:
        if path.exists():
            data = path.read_bytes()
        else:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.content
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return Image.open(BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def _detect_face(img):
    """(cx, cy, size) of the largest face, or None (needs OpenCV)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        gray = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                         minSize=(max(20, gray.shape[1] // 10),) * 2)
    except Exception:
        return None
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return x + w / 2, y + h / 2, max(w, h)


def face_crop(img, zoom: float = 1.9):
    """Square crop around the face. zoom = crop size / face size (bigger = more margin)."""
    w, h = img.size
    face = _detect_face(img)
    if face:
        cx, cy, size = face
        side = size * zoom
        cy -= size * 0.08                      # a little more room for the hair than for the chin
    elif h > w * 1.05:                         # portrait, waist-up photo: head near the top
        side, cx, cy = 0.58 * w, w / 2, 0.25 * h
    elif w > h * 1.05:                         # landscape head-and-shoulders (e.g. NBA headshots)
        side, cx, cy = 0.75 * h, w / 2, 0.40 * h
    else:
        side, cx, cy = 0.62 * w, w / 2, 0.33 * h
    side = min(side, w, h)
    left = min(max(cx - side / 2, 0), w - side)
    top = min(max(cy - side / 2, 0), h - side)
    return img.crop((int(left), int(top), int(left + side), int(top + side)))


def to_data_uri(img, size: int = 128) -> str:
    img = img.copy()
    img.thumbnail((size, size))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def face_uri(url: str | None) -> str | None:
    """Face-cropped photo as a data URI for Plotly (None if the photo is unavailable)."""
    img = load_image(url)
    return to_data_uri(face_crop(img)) if img is not None else None


def crest_uri(url: str | None) -> str | None:
    """Crest as a data URI (no crop). None if the image cannot be loaded."""
    img = load_image(url)
    return to_data_uri(img, size=200) if img is not None else None


def prepare(url: str | None, kind: str) -> str | None:
    """'photo' -> face crop; 'crest' -> whole image. Already-prepared data URIs pass through."""
    if isinstance(url, str) and url.startswith("data:image"):
        return url
    return face_uri(url) if kind == "photo" else crest_uri(url)
