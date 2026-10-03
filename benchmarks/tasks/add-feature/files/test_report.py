from report import summarize


def test_summarize():
    assert summarize([{"amount": 2}, {"amount": 3}]) == 5
