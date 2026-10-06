"""
Start interactive Joshu with a scripted model, for the terminal tests.

JOSHU_TEST_SCRIPT names a JSON file: a list of turns, each
{"content": "...", "tool_calls": [{"name": ..., "arguments": {...}}]}.
Every model call takes the next turn; when they run out the model says
"(script done)".
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from joshu.core import agent as agent_module  # noqa: E402
from joshu.core.llm_client import AssistantTurn, ToolCall  # noqa: E402


class ScriptedClient:
    model = "scripted-model"
    context_window = 128000

    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def complete(self, messages, tools=None, *, on_text=None, **kwargs):
        if not self.turns:
            turn = AssistantTurn(content="(script done)", finish_reason="stop")
        else:
            spec = self.turns.pop(0)
            self.calls += 1
            turn = AssistantTurn(
                content=spec.get("content", ""),
                tool_calls=[
                    ToolCall(
                        id=f"call_{self.calls}_{i}",
                        name=call["name"],
                        arguments=json.dumps(call.get("arguments", {})),
                    )
                    for i, call in enumerate(spec.get("tool_calls", []))
                ],
                finish_reason="tool_calls" if spec.get("tool_calls") else "stop",
            )
        if on_text and turn.content:
            on_text(turn.content)
        return turn


def main() -> None:
    turns = json.loads(Path(os.environ["JOSHU_TEST_SCRIPT"]).read_text(encoding="utf-8"))
    client = ScriptedClient(turns)
    agent_module.create_chat_client = lambda *args, **kwargs: client

    from joshu.ui.interactive.interactive_mode import InteractiveMode

    InteractiveMode("scripted-model").start()


if __name__ == "__main__":
    main()
