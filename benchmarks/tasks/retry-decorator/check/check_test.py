import pytest
from retry import retry


def flaky(failures, error=OSError):
    state = {"calls": 0}

    def call():
        state["calls"] += 1
        if state["calls"] <= failures:
            raise error(f"fail {state['calls']}")
        return "ok"

    return call, state


def test_retries_until_success_with_backoff():
    sleeps = []
    call, state = flaky(3)
    wrapped = retry(5, backoff=0.5, sleep=sleeps.append)(call)
    assert wrapped() == "ok"
    assert state["calls"] == 4 and wrapped.attempts == 4
    assert sleeps == [0.5, 1.0, 2.0]


def test_raises_the_last_error():
    call, state = flaky(10)
    wrapped = retry(3, sleep=lambda s: pytest.fail("no sleep when backoff is 0"))(call)
    with pytest.raises(OSError, match="fail 3"):
        wrapped()
    assert state["calls"] == 3 and wrapped.attempts == 3


def test_other_exceptions_are_not_retried():
    call, state = flaky(1, error=KeyError)
    wrapped = retry(4, exceptions=(OSError,))(call)
    with pytest.raises(KeyError):
        wrapped()
    assert state["calls"] == 1 and wrapped.attempts == 1


def test_arguments_and_metadata():
    @retry(2)
    def add(a, b=1):
        """Adds."""
        return a + b

    assert add(2, b=3) == 5 and add.attempts == 1
    assert add.__name__ == "add" and add.__doc__ == "Adds."


def test_validation():
    with pytest.raises(ValueError):
        retry(0)
    with pytest.raises(ValueError):
        retry(2, backoff=-1)
