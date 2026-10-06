"""Semantic versions (see SPEC.md)."""

from typing import Iterable, NamedTuple, Tuple


class Version(NamedTuple):
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()


def parse(text: str) -> Version:
    """Parse a version string; ValueError if it is invalid."""
    raise NotImplementedError


def compare(a: str, b: str) -> int:
    """-1 if a < b, 0 if equal, 1 if a > b (strings, parsed first)."""
    raise NotImplementedError


def latest(versions: Iterable[str]) -> str:
    """The highest version as given; ValueError for an empty input or an invalid version."""
    raise NotImplementedError
