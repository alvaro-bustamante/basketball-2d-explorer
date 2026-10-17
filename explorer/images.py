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


CROP_VERSION = 2   # bump when the crop logic changes (refreshes the app's image cache)
YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")


def _silhouette_head(img):
    """(cx, top, head_width) from the transparency of a cut-out photo, or None."""
    import numpy as np

    alpha = np.asarray(img.getchannel("A")) > 40
    h, w = alpha.shape
    if alpha.mean() > 0.9 or not alpha.any():          # not a cut-out
        return None
    rows = np.where(alpha.sum(axis=1) > w * 0.02)[0]
    if len(rows) == 0:
        return None
    top = rows[0]
    band = alpha[top: top + int(0.12 * h)]               # the head, above the shoulders
    widths = band.sum(axis=1)
    head_w = float(np.percentile(widths, 90))
    cols = np.where(band.any(axis=0))[0]
    cx = float(np.average(np.arange(w), weights=band.sum(axis=0))) if len(cols) else w / 2
    return cx, float(top), max(head_w, w * 0.12)


_yunet = None


def _detect_face(img):
    """(cx, cy, size) of the largest face with OpenCV's YuNet detector, or None.
    The small model (~230 KB) is downloaded once to data/cache/."""
    global _yunet
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    if not hasattr(cv2, "FaceDetectorYN"):
        return None
    try:
        if _yunet is None:
            model = CACHE_DIR.parent / "face_detection_yunet.onnx"
            if not model.exists():
                r = requests.get(YUNET_URL, headers=HEADERS, timeout=30)
                r.raise_for_status()
                model.parent.mkdir(parents=True, exist_ok=True)
                model.write_bytes(r.content)
            _yunet = cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.7)
        bg = img.copy()
        rgb = np.asarray(bg.convert("RGB"))[:, :, ::-1].copy()
        _yunet.setInputSize((rgb.shape[1], rgb.shape[0]))
        _, faces = _yunet.detect(rgb)
    except Exception:
        _yunet = False if _yunet is None else _yunet
        return None
    if faces is None or len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])[:4]
    return x + w / 2, y + h / 2, max(w, h)


def face_crop(img, zoom: float = 2.0):
    """Square crop with the face filling most of it.

    1. Cut-out photos (transparent background: EuroLeague, NBA): head found from the silhouette.
    2. Other photos: OpenCV face detector (YuNet) if available.
    3. Otherwise a top-anchored square (close-up photos such as the ACB ones stay whole).
    """
    w, h = img.size
    head = _silhouette_head(img) if img.mode == "RGBA" else None
    if head:
        cx, top, head_w = head
        side = head_w * 2.1
        cy = top - side * 0.10 + side / 2
    else:
        face = _detect_face(img) if _yunet is not False else None
        if face:
            cx, cy, size = face
            side = size * zoom
            cy -= size * 0.08                  # a little more room for the hair than for the chin
        else:
            side = min(w, h)
            cx, cy = w / 2, side / 2
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
