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


def copy_text(text: str) -> str:
    """
    Put `text` on the clipboard; returns how ("clip", "pbcopy", ... or "terminal"
    for the OSC 52 escape sequence, which most terminals accept even over SSH).
    """
    import base64
    import shutil
    import subprocess
    import sys

    candidates = []
    if sys.platform == "win32":
        candidates.append(["clip"])
    elif sys.platform == "darwin":
        candidates.append(["pbcopy"])
    else:
        candidates += [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]]
    for argv in candidates:
        if shutil.which(argv[0]) is None:
            continue
        # clip.exe reads the console code page; UTF-16 with a BOM keeps any text intact
        data = b"\xff\xfe" + text.encode("utf-16-le") if argv[0] == "clip" else text.encode("utf-8")
        try:
            if subprocess.run(argv, input=data, capture_output=True, timeout=10).returncode == 0:
                return argv[0]
        except (OSError, subprocess.SubprocessError):
            continue
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    sys.stdout.write(f"\x1b]52;c;{encoded}\x07")
    sys.stdout.flush()
    return "terminal"


def image_reference(path: Path) -> str:
    """The text that attaches `path` to a message."""
    text = str(path)
    return f'@"{text}" ' if " " in text else f"@{text} "
