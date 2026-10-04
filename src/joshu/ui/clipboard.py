"""
Pasting images from the clipboard (Alt+V or /paste in interactive mode).

The image is saved under ~/.joshu/pastes and attached to the message as an
`@"path"` reference. Reading the clipboard needs Pillow (`pip install pillow`);
on Linux, Pillow also needs `wl-paste` (Wayland) or `xclip` (X11).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from joshu.core.images import is_image_path


class ClipboardError(Exception):
    """The clipboard couldn't be read."""


def paste_directory() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / "pastes"


def grab_clipboard_image(directory: Optional[Path] = None) -> Optional[Path]:
    """
    Save the clipboard's image (or the first copied image file) and return its
    path; None when the clipboard holds no image.

    Raises:
        ClipboardError: Pillow is missing or the clipboard can't be read.
    """
    try:
        from PIL import Image, ImageGrab
    except ImportError as e:
        raise ClipboardError("Pasting images needs Pillow: pip install pillow") from e

    try:
        content = ImageGrab.grabclipboard()
    except Exception as e:  # e.g. no xclip / wl-paste on Linux
        raise ClipboardError(f"Couldn't read the clipboard: {e}") from e

    if content is None:
        return None
    if isinstance(content, list):  # files copied in the file manager
        for item in content:
            if is_image_path(str(item)) and Path(item).is_file():
                return Path(item)
        return None
    if not isinstance(content, Image.Image):
        return None

    directory = directory or paste_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"paste-{datetime.now():%Y%m%d-%H%M%S-%f}.png"
    content.save(path, "PNG")
    return path


def image_reference(path: Path) -> str:
    """The text that attaches `path` to a message."""
    text = str(path)
    return f'@"{text}" ' if " " in text else f"@{text} "
