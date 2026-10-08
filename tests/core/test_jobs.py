"""Background jobs: a request run detached in its own worktree, applied later."""

import json
import subprocess
import sys
import time

import pytest
from test_agent_loop import FakeClient, call, text
from typer.testing import CliRunner

from joshu.core import jobs
from joshu.core.jobs import JobError


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "a.py").write_text("A = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    monkeypatch.chdir(root)
    yield root
    from joshu.tools import filesystem_tools

    filesystem_tools._workspace_root = None


def replace(old, new):
    return call("replace", path="a.py", old_string=old, new_string=new)


def test_run_then_apply(repo):
    job = jobs.start("set A to 2", repo, permission_mode="accept_edits", spawn=False)
    assert job.status == jobs.RUNNING and job.branch.startswith("joshu/job-")
    finished = jobs.run(job.id, client=FakeClient([replace("A = 1", "A = 2"), text("A is 2 now.")]))
    assert finished.status == jobs.DONE and finished.result == "A is 2 now."
    assert finished.files == ["a.py"] and "a.py" in finished.stat
    assert not jobs.Path(finished.worktree).exists()  # the worktree is gone, the branch stays
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 1\n"  # not applied yet
    assert job.branch in git(repo, "branch")

    applied = jobs.apply(job.id[:4])  # a prefix works
    assert applied.applied and (repo / "a.py").read_text(encoding="utf-8") == "A = 2\n"
    assert job.branch not in git(repo, "branch")
    with pytest.raises(JobError, match="already applied"):
        jobs.apply(job.id)


def test_uncommitted_work_is_seen_and_kept(repo):
    (repo / "a.py").write_text("A = 1\nOTHER = 1\n", encoding="utf-8")
    job = jobs.start("set A to 2", repo, spawn=False)
    jobs.run(job.id, client=FakeClient([replace("A = 1", "A = 2"), text("done")]))
    jobs.apply(job.id)
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 2\nOTHER = 1\n"


def test_failures_and_no_changes(repo):
    class Broken:
        model = "broken"

        def complete(self, *args, **kwargs):
            raise RuntimeError("model down")

    job = jobs.start("anything", repo, spawn=False)
    failed = jobs.run(job.id, client=Broken())
    assert failed.status == jobs.FAILED and "model down" in failed.error
    assert job.branch not in git(repo, "branch")  # nothing kept
    with pytest.raises(JobError, match="only finished jobs"):
        jobs.apply(job.id)

    quiet = jobs.start("look only", repo, spawn=False)
    done = jobs.run(quiet.id, client=FakeClient([text("Nothing to change.")]))
    with pytest.raises(JobError, match="changed no files"):
        jobs.apply(done.id)


def test_stop_and_lost(repo):
    job = jobs.start("long one", repo, spawn=False)
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    job.pid = sleeper.pid
    job.save()
    stopped = jobs.stop(job.id)
    assert stopped.status == jobs.STOPPED
    sleeper.wait(timeout=10)
    assert job.branch not in git(repo, "branch")

    lost = jobs.start("vanished", repo, spawn=False)
    lost.pid = sleeper.pid  # a process that is gone
    lost.save()
    assert jobs.load(lost.id).status == jobs.LOST


def test_detached_process_records_its_outcome(repo, monkeypatch):
    # No model can be reached here: the job's own process records the failure
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.setenv("JOSHU_PROVIDER", "nvidia")
    job = jobs.start("anything", repo)
    assert job.pid and job.log_path.parent.is_dir()
    deadline = time.time() + 90
    while time.time() < deadline and jobs.load(job.id).status == jobs.RUNNING:
        time.sleep(0.5)
    final = jobs.load(job.id)
    assert final.status == jobs.FAILED and final.finished_at and final.error, final


def test_cli_and_slash(repo):
    from joshu.ui.cli import app

    job = jobs.start("set A to 2", repo, spawn=False)
    jobs.run(job.id, client=FakeClient([replace("A = 1", "A = 2"), text("A is 2 now.")]))
    runner = CliRunner()
    listed = runner.invoke(app, ["jobs"])
    assert job.id in listed.output and "done" in listed.output
    shown = runner.invoke(app, ["jobs", "show", job.id])
    assert "A is 2 now." in shown.output and f"joshu jobs apply {job.id}" in shown.output
    assert runner.invoke(app, ["jobs", "show", "nope"]).exit_code == 1
    assert runner.invoke(app, ["jobs", "apply", job.id]).exit_code == 0
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 2\n"
    assert runner.invoke(app, ["jobs", "stop", job.id]).exit_code == 1  # not running
    assert json.loads((job.directory / "job.json").read_text(encoding="utf-8"))["applied"]


# ------------------------------------------------------------------ approvals


def answer_when_asked(job_id, allow, seen=None):
    """Like a user running `joshu jobs approve|deny` once the job asks."""
    import threading

    def answer():
        deadline = time.time() + 20
        while time.time() < deadline:
            job = jobs.load(job_id)
            if job.pending:
                if seen is not None:
                    seen.append(dict(job.pending))
                jobs.decide(job_id, allow)
                return
            time.sleep(0.1)

    thread = threading.Thread(target=answer, daemon=True)
    thread.start()
    return thread


def test_waits_for_approval(repo):
    job = jobs.start("x", repo, spawn=False)
    seen = []
    thread = answer_when_asked(job.id, True, seen)
    assert jobs.wait_for_approval(job, "run_shell_command", {"command": "make"}, poll=0.05)
    thread.join(5)
    assert seen[0]["summary"] == "make" and jobs.load(job.id).pending is None

    thread = answer_when_asked(job.id, False)
    assert not jobs.wait_for_approval(job, "run_shell_command", {"command": "rm x"}, poll=0.05)
    thread.join(5)


def test_unanswered_approval_is_denied(repo):
    from joshu.core.config import get_config_manager

    get_config_manager().set("job_approval_timeout", 1)
    job = jobs.start("x", repo, spawn=False)
    started = time.time()
    assert not jobs.wait_for_approval(job, "run_shell_command", {"command": "make"}, poll=0.05)
    assert time.time() - started < 5 and jobs.load(job.id).pending is None
    with pytest.raises(JobError, match="isn't waiting"):
        jobs.decide(job.id, True)


def test_a_job_runs_an_approved_command(repo):
    job = jobs.start("print hello", repo, permission_mode="accept_edits", spawn=False)
    command = f'"{sys.executable}" -c "print(42)"'
    thread = answer_when_asked(job.id, True)
    done = jobs.run(
        job.id,
        client=FakeClient([call("run_shell_command", command=command), text("It printed 42.")]),
    )
    thread.join(5)
    assert done.status == jobs.DONE and done.result == "It printed 42."
    session = __import__("joshu.core.sessions", fromlist=["x"]).load_session(done.session_id)
    outputs = [m["content"] for m in session["messages"] if m.get("role") == "tool"]
    assert "42" in outputs[0]


def test_cli_shows_and_answers_a_waiting_job(repo):
    from joshu.ui.cli import app

    job = jobs.start("x", repo, spawn=False)
    job.pending = {"tool": "run_shell_command", "summary": "npm test", "asked_at": "now"}
    job.save()
    runner = CliRunner()
    listed = runner.invoke(app, ["jobs"]).output
    assert "waiting for you" in listed and "npm test" in listed and "jobs approve" in listed
    assert runner.invoke(app, ["jobs", "deny", job.id]).exit_code == 0
    assert json.loads((job.directory / "decision.json").read_text(encoding="utf-8")) == {
        "allow": False
    }
