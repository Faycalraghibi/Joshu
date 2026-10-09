"""
Agent teams: named teammates working at the same time, talking to each other.

The lead (the main agent) starts teammates with `spawn_teammate`. Each one is
a sub-agent on its own thread that keeps its conversation between runs: when
a run ends it goes idle, and its answer is sent to the lead. Every member has
`send_message` (to a teammate, "lead" or "all"): a running member gets its
messages between turns, an idle teammate starts a new run with them. The
`team_tasks` list (add, claim, done) is shared, so members can split the work
and see who has what.

Teammates can't ask for approval (they work in the background): what would
ask is refused, as for background tasks. With `edit`, each run works in its
own git worktree, applied to the working tree when the run ends.
"""

from __future__ import annotations

import contextvars
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

LEAD = "lead"
MAX_TEAMMATES = 5


@dataclass
class TeamTask:
    id: int
    title: str
    status: str = "open"  # open, claimed, done
    owner: str = ""
    note: str = ""


@dataclass
class Member:
    """A teammate. `id`, `description` and `done` match BackgroundTask (for the lead)."""

    name: str
    description: str  # its role
    edit: bool = False
    agent: Any = None  # its Agent (read-only teammates keep one for good)
    history: List[Dict[str, Any]] = field(default_factory=list)  # editing ones: carried over
    done: threading.Event = field(default_factory=threading.Event)  # set while idle
    inbox: List[str] = field(default_factory=list)
    runs: int = 0
    last: str = ""

    @property
    def id(self) -> str:
        return self.name


class Team:
    """The members, their inboxes and the shared task list."""

    def __init__(self, runner: Callable[[Member, str], str]) -> None:
        """
        Args:
            runner: Runs `member` on one prompt and returns its answer (the lead's
                Agent provides it); called on the member's thread
        """
        self.runner = runner
        self.members: Dict[str, Member] = {}
        self.tasks: List[TeamTask] = []
        self.lead_inbox: List[str] = []
        self.lock = threading.RLock()

    # ------------------------------------------------------------ members

    def add(self, member: Member, first_prompt: str) -> None:
        with self.lock:
            self.members[member.name] = member
        self._start(member, first_prompt)

    def running(self) -> List[Member]:
        with self.lock:
            return [m for m in self.members.values() if not m.done.is_set()]

    def _start(self, member: Member, prompt: str) -> None:
        member.done.clear()

        def work() -> None:
            text = prompt
            while True:
                try:
                    answer = self.runner(member, text)
                except Exception as e:  # reported to the lead: nothing waits on the thread
                    answer = f"(failed: {e})"
                with self.lock:
                    member.runs += 1
                    member.last = answer
                    self.lead_inbox.append(f"[Teammate {member.name} finished a run]\n{answer}")
                    if not member.inbox:
                        member.done.set()
                        return
                    # Messages that came after its last turn: go on with them
                    text = "\n\n".join(member.inbox)
                    member.inbox.clear()

        context = contextvars.copy_context()  # the workspace root follows the thread
        threading.Thread(
            target=context.run, args=(work,), name=f"joshu-team-{member.name}", daemon=True
        ).start()

    # ------------------------------------------------------------- messages

    def send(self, sender: str, to: str, message: str) -> str:
        """Deliver a message; returns what the sender is told."""
        note = f"[Message from {sender}]\n{message}"
        with self.lock:
            if to == "all":
                names = [n for n in [LEAD, *self.members] if n != sender]
            else:
                names = [to]
            unknown = [n for n in names if n != LEAD and n not in self.members]
            if unknown:
                known = ", ".join([LEAD, *self.members])
                return f"Error: no teammate '{unknown[0]}' (team: {known})"
            woken = []
            for name in names:
                if name == LEAD:
                    self.lead_inbox.append(note)
                    continue
                member = self.members[name]
                if member.done.is_set():
                    woken.append(name)
                    self._start(member, note)
                else:
                    member.inbox.append(note)
        sent = ", ".join(names) or "nobody"
        return f"Sent to {sent}." + (f" Woke up: {', '.join(woken)}." if woken else "")

    def take(self, name: str) -> List[str]:
        """Messages waiting for `name` (removed)."""
        with self.lock:
            if name == LEAD:
                taken, self.lead_inbox = self.lead_inbox, []
                return taken
            member = self.members.get(name)
            if member is None:
                return []
            taken, member.inbox = member.inbox, []
            return taken

    # ---------------------------------------------------------------- tasks

    def task_action(
        self, who: str, action: str, title: str = "", task_id: int = 0, note: str = ""
    ) -> str:
        with self.lock:
            if action == "add":
                if not title.strip():
                    return "Error: add needs a title"
                task = TeamTask(len(self.tasks) + 1, title.strip())
                self.tasks.append(task)
                return f"Added task {task.id}: {task.title}"
            if action in ("claim", "done"):
                task = next((t for t in self.tasks if t.id == int(task_id or 0)), None)
                if task is None:
                    return f"Error: no task {task_id}"
                if action == "claim":
                    if task.status != "open" and task.owner != who:
                        return f"Error: task {task.id} is {task.status} by {task.owner}"
                    task.status, task.owner = "claimed", who
                else:
                    task.status, task.owner = "done", task.owner or who
                    task.note = note.strip()
                return f"Task {task.id} is {task.status} ({task.owner})."
            if action != "list":
                return "Error: action is list, add, claim, done or wait"
            return self.describe()

    def describe(self) -> str:
        with self.lock:
            lines = ["Team:"]
            for member in self.members.values():
                state = "idle" if member.done.is_set() else "working"
                lines.append(
                    f"- {member.name} ({state}, {member.runs} run(s)): {member.description}"
                )
            lines.append("Tasks:" if self.tasks else "Tasks: none yet")
            for task in self.tasks:
                owner = f" [{task.owner}]" if task.owner else ""
                note = f" ({task.note})" if task.note else ""
                lines.append(f"{task.id}. [{task.status}]{owner} {task.title}{note}")
            return "\n".join(lines)


def wait_idle(team: Team, timeout: float) -> bool:
    """Wait until no member is working (for tests and scripts)."""
    deadline = time.monotonic() + timeout
    while team.running():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    return True


def member_prompt(name: str, description: str, others: List[str]) -> str:
    """What a teammate is told about the team, at the start of its instructions."""
    return (
        f"You are {name}, a teammate in a team led by the main agent ('lead'). Your role: "
        f"{description}\nOther members: {', '.join(others) or 'none yet'}. Use send_message to "
        "talk to them or the lead, and team_tasks to see, claim and finish shared tasks (claim "
        "one before working on it). Messages to you arrive between your turns. When you finish, "
        "your final reply goes to the lead."
    )
