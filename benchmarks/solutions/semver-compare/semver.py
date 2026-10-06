"""Semantic versions (see SPEC.md)."""

import re
from typing import Iterable, NamedTuple, Tuple

_NUMBER = r"(0|[1-9][0-9]*)"
_IDENT = r"[0-9A-Za-z-]+"
_PATTERN = re.compile(
    rf"^{_NUMBER}\.{_NUMBER}\.{_NUMBER}"
    rf"(?:-({_IDENT}(?:\.{_IDENT})*))?"
    rf"(?:\+({_IDENT}(?:\.{_IDENT})*))?$"
)


class Version(NamedTuple):
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()


def parse(text: str) -> Version:
    """Parse a version string; ValueError if it is invalid."""
    match = _PATTERN.match(text)
    if not match:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch, pre, build = match.groups()
    prerelease = tuple(pre.split(".")) if pre else ()
    for ident in prerelease:
        if ident.isdigit() and len(ident) > 1 and ident.startswith("0"):
            raise ValueError(f"invalid version: {text!r}")
    return Version(
        int(major), int(minor), int(patch), prerelease, tuple(build.split(".")) if build else ()
    )


def _ident_key(ident: str):
    return (0, int(ident), "") if ident.isdigit() else (1, 0, ident)


def _cmp_pre(a: Tuple[str, ...], b: Tuple[str, ...]) -> int:
    for x, y in zip(a, b):
        kx, ky = _ident_key(x), _ident_key(y)
        if kx != ky:
            return -1 if kx < ky else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def compare(a: str, b: str) -> int:
    """-1 if a < b, 0 if equal, 1 if a > b (strings, parsed first)."""
    va, vb = parse(a), parse(b)
    core_a, core_b = va[:3], vb[:3]
    if core_a != core_b:
        return -1 if core_a < core_b else 1
    if va.prerelease and not vb.prerelease:
        return -1
    if vb.prerelease and not va.prerelease:
        return 1
    return _cmp_pre(va.prerelease, vb.prerelease)


def latest(versions: Iterable[str]) -> str:
    """The highest version as given; ValueError for an empty input or an invalid version."""
    best = None
    for version in versions:
        parse(version)
        if best is None or compare(version, best) > 0:
            best = version
    if best is None:
        raise ValueError("no versions")
    return best
