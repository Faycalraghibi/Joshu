"""
Questions the agent asks the user, with choices.

When a decision is the user's (an unclear requirement, several reasonable
designs), the model calls the `ask_user` tool with one to four questions, each
with two to six options; a question can allow several answers. The interface
(the terminal, or the SDK's `ask_user` callback) shows them and returns what
the user picked, or typed after choosing "Other".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MAX_QUESTIONS = 4
MIN_OPTIONS = 2
MAX_OPTIONS = 6

# A question's answer: the chosen labels, or the text the user typed
Answer = Union[List[str], str]

ASK_TOOL_DESCRIPTION = (
    "Ask the user to choose when a decision is theirs: an unclear requirement, or "
    "several reasonable approaches with different trade-offs. Give 2-6 short options "
    "per question (the user can also type their own answer); set multi_select when "
    "several can apply. Don't ask what you can find out by reading the code."
)

ASK_PROMPT_RULE = (
    "When a decision is the user's (an unclear requirement, several valid approaches), "
    "ask with `ask_user` and give choices instead of guessing; don't ask about what you "
    "can find out yourself."
)

PARAMETERS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_QUESTIONS,
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question, ending with ?"},
                    "header": {
                        "type": "string",
                        "description": "A 1-3 word label, e.g. 'Database'",
                    },
                    "options": {
                        "type": "array",
                        "minItems": MIN_OPTIONS,
                        "maxItems": MAX_OPTIONS,
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["label"],
                        },
                    },
                    "multi_select": {
                        "type": "boolean",
                        "description": "True when several options can be chosen",
                    },
                },
                "required": ["question", "options"],
            },
        }
    },
    "required": ["questions"],
}


class AskError(ValueError):
    """The model's questions are malformed."""


@dataclass
class Question:
    question: str
    options: List[Tuple[str, str]] = field(default_factory=list)  # (label, description)
    multi_select: bool = False
    header: str = ""


def parse_questions(raw: Any) -> List[Question]:
    """Validate the tool's `questions` argument."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError as e:
            raise AskError("questions must be a list of objects") from e
    if not isinstance(raw, list) or not raw:
        raise AskError("questions must be a non-empty list")
    if len(raw) > MAX_QUESTIONS:
        raise AskError(f"ask at most {MAX_QUESTIONS} questions at a time")
    questions = []
    for item in raw:
        if not isinstance(item, dict) or not str(item.get("question", "")).strip():
            raise AskError("each question needs a 'question' text")
        options = []
        for option in item.get("options") or []:
            if isinstance(option, str):
                option = {"label": option}
            if not isinstance(option, dict) or not str(option.get("label", "")).strip():
                raise AskError("each option needs a 'label'")
            options.append(
                (str(option["label"]).strip(), str(option.get("description") or "").strip())
            )
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            raise AskError(f"give {MIN_OPTIONS}-{MAX_OPTIONS} options per question")
        questions.append(
            Question(
                question=str(item["question"]).strip(),
                options=options,
                multi_select=bool(item.get("multi_select", False)),
                header=str(item.get("header") or "").strip()[:30],
            )
        )
    return questions


def format_answers(
    questions: Sequence[Question], answers: Optional[Sequence[Optional[Answer]]]
) -> str:
    """What the tool returns to the model."""
    if answers is None:
        return json.dumps(
            {
                "answered": False,
                "message": "The user didn't answer. Make a reasonable choice, say which in "
                "your reply, and continue.",
            }
        )
    result = []
    for question, answer in zip(questions, answers):
        entry: Dict[str, Any] = {"question": question.question}
        if answer is None:
            entry["answer"] = None
            entry["note"] = "skipped: choose yourself and say which"
        elif isinstance(answer, str):
            entry["answer"] = answer
            entry["note"] = "typed by the user"
        else:
            entry["answer"] = list(answer) if question.multi_select else answer[0]
        result.append(entry)
    return json.dumps({"answered": True, "answers": result}, ensure_ascii=False)
