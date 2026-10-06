"""Leaderboard of a timed quiz."""

from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class Entry:
    name: str
    score: int
    seconds: float  # time taken; less is better


def standings(entries: Sequence[Entry]) -> List[Tuple[int, Entry]]:
    """
    (rank, entry) pairs, best first.

    Order: higher score first; on equal score, less time first; on equal
    score and time, by name ignoring case (then by name as written, so the
    order is always the same).
    Ranks are "competition" ranks: entries equal on score and time share a
    rank, and the next rank skips the shared places (1, 2, 2, 4).
    """
    ordered = sorted(entries, key=lambda e: (-e.score, -e.seconds, e.name))
    result = []
    rank = 0
    previous = None
    for entry in ordered:
        if (entry.score, entry.seconds) != previous:
            rank += 1
            previous = (entry.score, entry.seconds)
        result.append((rank, entry))
    return result
