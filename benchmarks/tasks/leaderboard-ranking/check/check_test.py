from leaderboard import Entry, standings


def names(result):
    return [(rank, e.name) for rank, e in result]


def test_time_breaks_ties_less_first():
    result = standings([Entry("a", 5, 30.0), Entry("b", 5, 20.0), Entry("c", 7, 99.0)])
    assert names(result) == [(1, "c"), (2, "b"), (3, "a")]


def test_competition_ranks():
    result = standings(
        [
            Entry("w", 9, 10),
            Entry("x", 8, 10),
            Entry("y", 8, 10),
            Entry("z", 7, 10),
            Entry("v", 7, 10),
        ]
    )
    assert names(result) == [(1, "w"), (2, "x"), (2, "y"), (4, "v"), (4, "z")]


def test_names_ignore_case_then_as_written():
    result = standings(
        [Entry("bob", 1, 1), Entry("Alice", 1, 1), Entry("alice", 1, 1), Entry("Bea", 1, 1)]
    )
    assert names(result) == [(1, "Alice"), (1, "alice"), (1, "Bea"), (1, "bob")]


def test_empty():
    assert standings([]) == []
