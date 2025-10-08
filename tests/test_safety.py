from opencli.core.safety import assess_command_safety


def test_safe_command():
    report = assess_command_safety("du -sh .")
    assert report.safe


def test_risky_rm_blocked():
    report = assess_command_safety("sudo rm -rf /")
    assert not report.safe
    assert len(report.reasons) >= 1


