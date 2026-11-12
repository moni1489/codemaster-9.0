"""Демонстрационные изображения: заглушки Pillow с водяным знаком «ДЕМО» и реальные фото
со свободной лицензией из seed/photos (подпись с авторством, см. seed/SOURCES.md).
"""

from __future__ import annotations

import io
import math
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "C:/Windows/Fonts/times.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


@lru_cache(maxsize=16)
def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _band(img: Image.Image, text: str) -> Image.Image:
    w, h = img.size
    out = img.convert("RGBA")
    d = ImageDraw.Draw(out)
    d.rectangle([0, h - 44, w, h], fill=(20, 20, 20, 200))
    d.text((16, h - 22), text, font=font(20), fill=(240, 236, 225), anchor="lm")
    return out.convert("RGB")


def _watermark(img: Image.Image, label: str) -> Image.Image:
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(max(w, h) // 7)
    d.text((w / 2, h / 2), "ДЕМО", font=f, fill=(150, 30, 30, 70), anchor="mm")
    layer = layer.rotate(28, resample=Image.Resampling.BICUBIC)
    return _band(Image.alpha_composite(img.convert("RGBA"), layer), f"Демонстрационная запись · {label}")


def _paper(w: int, h: int, rnd: random.Random) -> Image.Image:
    base = (232 + rnd.randint(-6, 6), 222 + rnd.randint(-6, 6), 196 + rnd.randint(-8, 8))
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    for _ in range(1800):
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = rnd.randint(-18, 8)
        d.point((x, y), fill=(base[0] + c, base[1] + c, base[2] + c))
    return img


def _photo(w: int, h: int, rnd: random.Random) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    horizon = int(h * rnd.uniform(0.55, 0.7))
    for y in range(h):
        t = y / h
        tone = int(200 - 90 * t) if y < horizon else int(120 - 40 * t)
        d.line([(0, y), (w, y)], fill=(tone + 20, tone + 8, tone - 15))
    x = 0
    while x < w:
        bw = rnd.randint(60, 180)
        bh = rnd.randint(80, int(h * 0.45))
        shade = rnd.randint(55, 105)
        d.rectangle([x, horizon - bh, x + bw, horizon], fill=(shade + 10, shade, shade - 12))
        for wy in range(horizon - bh + 15, horizon - 10, 26):
            for wx in range(x + 10, x + bw - 10, 22):
                if rnd.random() < 0.7:
                    d.rectangle([wx, wy, wx + 9, wy + 12], fill=(shade + 60, shade + 50, shade + 25))
        x += bw + rnd.randint(4, 30)
    if rnd.random() < 0.6:  # река
        d.rectangle([0, horizon + 30, w, horizon + 90], fill=(150, 140, 115))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    # зерно и виньетка
    px = img.load()
    assert px is not None
    for _ in range(w * h // 25):
        xx, yy = rnd.randrange(w), rnd.randrange(h)
        r, g, b = px[xx, yy]  # type: ignore[misc]
        n = rnd.randint(-25, 25)
        px[xx, yy] = (max(0, r + n), max(0, g + n), max(0, b + n))
    vign = Image.new("L", (w, h), 0)
    dv = ImageDraw.Draw(vign)
    dv.ellipse([-w * 0.15, -h * 0.2, w * 1.15, h * 1.2], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(min(w, h) // 8))
    return Image.composite(img, Image.new("RGB", (w, h), (30, 22, 14)), vign)


def _text_page(w: int, h: int, rnd: random.Random, title: str, page: int) -> Image.Image:
    img = _paper(w, h, rnd)
    d = ImageDraw.Draw(img)
    ink = (45, 40, 70)
    d.text((w / 2, 90), title[:60], font=font(30), fill=ink, anchor="mm")
    y = 160
    while y < h - 220:
        line_w = rnd.randint(int(w * 0.55), int(w * 0.85))
        x = 90 if rnd.random() > 0.15 else 140
        for _seg in range(rnd.randint(5, 11)):
            seg = rnd.randint(25, 90)
            if x + seg > 90 + line_w:
                break
            d.line([(x, y), (x + seg, y)], fill=ink, width=3)
            x += seg + rnd.randint(10, 18)
        y += rnd.choice([30, 32, 34])
    cx, cy = w - 220, h - 160
    d.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], outline=(110, 60, 140), width=5)
    d.ellipse([cx - 55, cy - 55, cx + 55, cy + 55], outline=(110, 60, 140), width=2)
    d.text((w / 2, h - 70), f"— {page} —", font=font(22), fill=ink, anchor="mm")
    return img


def _map(w: int, h: int, rnd: random.Random, title: str) -> Image.Image:
    img = _paper(w, h, rnd)
    d = ImageDraw.Draw(img)
    for gx in range(0, w, 70):
        d.line([(gx, 0), (gx, h)], fill=(200, 188, 160), width=1)
    for gy in range(0, h, 70):
        d.line([(0, gy), (w, gy)], fill=(200, 188, 160), width=1)
    pts = [(x, h * 0.55 + math.sin(x / 140 + rnd.random()) * 90) for x in range(0, w + 20, 20)]
    d.line(pts, fill=(90, 130, 170), width=26)
    for _ in range(28):
        x, y = rnd.randrange(60, w - 160), rnd.randrange(60, h - 160)
        if abs(y - h * 0.55) < 110:
            continue
        d.rectangle([x, y, x + rnd.randint(40, 120), y + rnd.randint(30, 90)], outline=(80, 60, 40), width=3)
    d.rectangle([30, 30, w - 30, h - 60], outline=(70, 50, 30), width=4)
    d.text((60, 70), title[:70], font=font(28), fill=(70, 50, 30), anchor="lm")
    return img


def _newspaper(w: int, h: int, rnd: random.Random, title: str) -> Image.Image:
    img = _paper(w, h, rnd)
    d = ImageDraw.Draw(img)
    ink = (30, 28, 26)
    masthead = "РУДНЫЙ АЛТАЙ" if "Рудный" in title or "газет" in title.lower() else "ГАЗЕТА"
    if "Коммунизм" in title or "тәуелсіздік" in title.lower() or "Қазақстан" in title:
        masthead = "КОММУНИЗМ ТУЫ"
    d.text((w / 2, 80), masthead, font=font(64), fill=ink, anchor="mm")
    d.line([(40, 130), (w - 40, 130)], fill=ink, width=4)
    d.text((w / 2, 165), title[:70], font=font(24), fill=ink, anchor="mm")
    d.line([(40, 195), (w - 40, 195)], fill=ink, width=2)
    cols = 4
    cw = (w - 80) // cols
    d.rectangle([50, 220, 50 + cw * 2 - 20, 520], fill=(120, 112, 98))
    for c in range(cols):
        x0 = 50 + c * cw
        y = 540 if c < 2 else 220
        while y < h - 60:
            d.line([(x0, y), (x0 + cw - 30 - rnd.randint(0, 40), y)], fill=ink, width=2)
            y += 18
    return img


def render(kind: str, key: str, title: str, page: int = 1) -> bytes:
    rnd = random.Random(f"{key}:{page}")  # noqa: S311 — детерминированная графика, не криптография
    if kind == "photo":
        img = _photo(1400, 980, rnd)
    elif kind == "map":
        img = _map(1400, 1000, rnd, title)
    elif kind == "newspaper":
        img = _newspaper(1000, 1400, rnd, title)
    else:
        img = _text_page(1000, 1400, rnd, title, page)
    img = _watermark(img, title[:80])
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue()


def render_photo(path: Path, credit: str) -> bytes:
    """Реальное фото (уменьшено) с подписью-атрибуцией внизу — требование CC BY / CC BY-SA."""
    with Image.open(path) as src:
        img = src.convert("RGB")
    img.thumbnail((1400, 1400))
    out = io.BytesIO()
    _band(img, f"Демо · {credit}").save(out, "JPEG", quality=85)
    return out.getvalue()
