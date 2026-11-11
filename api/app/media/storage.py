"""Файловое хранилище. Каталог STORAGE_DIR не монтируется как статика — файлы отдаются только через
эндпоинт с проверкой доступа (app.media.router)."""

from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.core.config import get_settings

VIEW_MAX_SIDE = 2000
THUMB_MAX_SIDE = 480

# Сигнатуры (magic bytes) разрешённых форматов: MIME определяется по содержимому, не по имени/заголовку
SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"%PDF-", 0, "application/pdf"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"II*\x00", 0, "image/tiff"),
    (b"MM\x00*", 0, "image/tiff"),
    (b"WEBP", 8, "image/webp"),
    (b"ftyp", 4, "video/mp4"),
    (b"ID3", 0, "audio/mpeg"),
]
IMAGE_MIMES = {"image/jpeg", "image/png", "image/tiff", "image/webp"}
EXT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tif",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "audio/mpeg": "mp3",
}


class UnsupportedFile(ValueError):
    pass


def sniff_mime(data: bytes) -> str:
    for sig, offset, mime in SIGNATURES:
        if data[offset : offset + len(sig)] == sig:
            if mime == "image/webp" and data[:4] != b"RIFF":
                continue
            return mime
    raise UnsupportedFile("Неподдерживаемый или повреждённый файл (сигнатура не распознана)")


def root() -> Path:
    path = Path(get_settings().storage_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(storage_key: str) -> Path:
    """Путь к файлу по ключу с защитой от выхода за пределы хранилища."""
    base = root()
    path = (base / storage_key).resolve()
    if base not in path.parents:
        raise PermissionError("storage key escapes storage root")
    return path


@dataclass
class Stored:
    storage_key: str
    mime: str
    size: int
    sha256: str
    width: int | None = None
    height: int | None = None


def _write(kind: str, data: bytes, mime: str) -> Stored:
    digest = hashlib.sha256(data).hexdigest()
    key = f"{kind}/{digest[:2]}/{uuid.uuid4().hex}.{EXT[mime]}"
    path = resolve(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    width = height = None
    if mime in IMAGE_MIMES:
        with Image.open(io.BytesIO(data)) as im:
            width, height = im.size
    return Stored(key, mime, len(data), digest, width, height)


def store_master(data: bytes, max_bytes: int | None = None) -> Stored:
    limit = max_bytes or get_settings().max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise UnsupportedFile(f"Файл больше лимита {limit // (1024 * 1024)} МБ")
    mime = sniff_mime(data)
    if mime in IMAGE_MIMES:
        # Pillow проверяет, что изображение действительно декодируется (защита от подделки сигнатуры)
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
        except Exception as exc:
            raise UnsupportedFile("Изображение повреждено") from exc
    return _write("master", data, mime)


def make_webp(data: bytes, max_side: int, quality: int = 80) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im.seek(0)
        img = im.convert("RGB")
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        img.save(out, "WEBP", quality=quality, method=4)
        return out.getvalue()


def store_derivatives(master_bytes: bytes) -> tuple[Stored, Stored]:
    """Облегчённая копия для просмотра и миниатюра (WebP)."""
    view = _write("view", make_webp(master_bytes, VIEW_MAX_SIDE), "image/webp")
    thumb = _write("thumb", make_webp(master_bytes, THUMB_MAX_SIDE, quality=70), "image/webp")
    return view, thumb
