"""
Images in user requests.

Attach an image by referencing it as `@path/to/image.png` anywhere in a
request, or with `joshu run --image PATH`. Images are sent as OpenAI-style
content parts (data URLs), which vision models behind OpenRouter and the
OpenAI, Gemini and Anthropic compatibility endpoints accept. The model must
support images.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# Rough context cost of one image, for compaction decisions (not billing)
IMAGE_TOKEN_ESTIMATE = 1500

# @path tokens: "@shot.png", "@docs/ui flow.png" is not supported (no spaces)
_REF_PATTERN = re.compile(r"(?<![\w@])@([^\s@]+)")

Content = Union[str, List[Dict[str, Any]]]


class ImageError(ValueError):
    """An image can't be attached."""


def is_image_path(path: Union[str, Path]) -> bool:
    return Path(path).suffix.lower() in IMAGE_TYPES


def image_part(path: Path) -> Dict[str, Any]:
    """
    An image content part for a chat message.

    Raises:
        ImageError: unsupported type, missing file, or larger than the limit.
    """
    media_type = IMAGE_TYPES.get(path.suffix.lower())
    if media_type is None:
        supported = ", ".join(sorted(IMAGE_TYPES))
        raise ImageError(f"{path.name}: unsupported image type (supported: {supported})")
    if not path.is_file():
        raise ImageError(f"Image not found: {path}")
    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ImageError(
            f"{path.name} is {size / 1_048_576:.1f} MB; images can be at most "
            f"{MAX_IMAGE_BYTES // 1_048_576} MB"
        )
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{data}"}}


def find_image_refs(text: str, cwd: Optional[Path] = None) -> Tuple[str, List[Path]]:
    """
    Pull `@path` references to existing image files out of a request.

    Returns:
        (text with each reference replaced by "[image: name]", image paths).
        References to other files, or to images that don't exist, are left
        untouched.
    """
    cwd = cwd or Path.cwd()
    paths: List[Path] = []

    def replace(match: re.Match) -> str:
        raw = match.group(1).rstrip(".,;:!?)")
        trailing = match.group(1)[len(raw) :]
        if not is_image_path(raw):
            return match.group(0)
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = cwd / path
        if not path.is_file():
            return match.group(0)
        paths.append(path)
        return f"[image: {path.name}]{trailing}"

    return _REF_PATTERN.sub(replace, text), paths


def build_user_content(text: str, images: Sequence[Path] = ()) -> Content:
    """Message content: plain text, or text plus image parts."""
    if not images:
        return text
    parts: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    parts.extend(image_part(path) for path in images)
    return parts


def message_text(content: Any) -> str:
    """The text of a message's content; images appear as "[image]"."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                pieces.append(str(part.get("text", "")))
            elif part.get("type") == "image_url":
                pieces.append("[image]")
        return "\n".join(pieces)
    return str(content)


def image_count(content: Any) -> int:
    if not isinstance(content, list):
        return 0
    return sum(1 for part in content if isinstance(part, dict) and part.get("type") == "image_url")
