import pathlib
import warnings

import pytest
from metrics import alerts, report
from metrics.stats import calc_avg, mean


def test_mean():
    assert mean([1, 2, 3]) == 2.0
    with pytest.raises(ValueError):
        mean([])


def test_alias_warns_and_works():
    with pytest.warns(DeprecationWarning):
        assert calc_avg([2, 4]) == 3.0


def test_package_uses_mean_without_warnings():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert report.summary([1, 2, 4]) == {"avg": 2.33, "spread": 3}
        assert alerts.too_slow([5, 7], 5.5)


def test_no_old_name_left():
    root = pathlib.Path(__file__).parent
    for path in [
        root / "metrics" / "report.py",
        root / "metrics" / "alerts.py",
        root / "README.md",
    ]:
        assert "calc_avg" not in path.read_text(encoding="utf-8"), path
    assert "mean" in (root / "README.md").read_text(encoding="utf-8")
