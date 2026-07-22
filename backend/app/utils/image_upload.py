from __future__ import annotations

from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError

FORMAT_SUFFIXES = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}
FORMAT_MIME_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}


def validate_raster_image(
    content: bytes,
    *,
    filename: str | None,
    content_type: str | None,
    max_width: int = 4096,
    max_height: int = 4096,
) -> str:
    if not content:
        raise ValueError("Image file is empty")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                detected_format = image.format
                width, height = image.size
                image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Invalid image content") from exc

    if detected_format not in FORMAT_SUFFIXES:
        raise ValueError("Unsupported image format")
    if width < 1 or height < 1 or width > max_width or height > max_height:
        raise ValueError(f"Image dimensions must be within {max_width}x{max_height}")

    expected_suffix = FORMAT_SUFFIXES[detected_format]
    supplied_suffix = Path(filename or "").suffix.lower()
    valid_suffixes = {expected_suffix}
    if detected_format == "JPEG":
        valid_suffixes.add(".jpeg")
    if supplied_suffix not in valid_suffixes:
        raise ValueError("Image extension does not match its content")
    if content_type != FORMAT_MIME_TYPES[detected_format]:
        raise ValueError("Image MIME type does not match its content")
    return expected_suffix


def delete_managed_upload(url: str | None, url_prefix: str, upload_dir: Path) -> None:
    if not url or not url.startswith(url_prefix):
        return
    filename = url.removeprefix(url_prefix)
    if not filename or "/" in filename or "\\" in filename:
        return
    candidate = (upload_dir / filename).resolve()
    if candidate.parent != upload_dir.resolve():
        return
    candidate.unlink(missing_ok=True)
