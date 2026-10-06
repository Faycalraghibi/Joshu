"""A response cut off by the output limit is continued, not taken as the answer."""

from joshu.core.agent import MAX_LENGTH_CONTINUES, MAX_OUTPUT_TOKENS, Agent
from joshu.core.llm_client import AssistantTurn, LLMError
from joshu.core.permissions import PermissionManager, PermissionMode


class LimitClient:
    """Answers `cut` turns cut off by the limit, then a real answer."""

    model = "fake"

    def __init__(self, cut=1, refuse_above=None):
        self.cut = cut
        self.refuse_above = refuse_above
        self.limits = []
        self.messages = []

    def complete(self, messages, tools=None, *, max_tokens=4096, **kwargs):
        if self.refuse_above and max_tokens > self.refuse_above:
            raise LLMError(f"HTTP 400: max_tokens {max_tokens} is too large")
        self.limits.append(max_tokens)
        self.messages.append([dict(m) for m in messages])
        if self.cut:
            self.cut -= 1
            return AssistantTurn(content="Let me think about the design...", finish_reason="length")
        return AssistantTurn(content="Done.", finish_reason="stop")


def make(client, max_tokens=8192):
    return Agent(
        permissions=PermissionManager(PermissionMode.BYPASS),
        client=client,
        max_tokens=max_tokens,
        persist=False,
    )


def test_cut_off_turn_continues_with_a_higher_limit():
    client = LimitClient(cut=1)
    response = make(client).run("implement the cache")
    assert response.text == "Done."
    assert client.limits == [8192, 16384]
    note = client.messages[1][-1]
    assert note["role"] == "user" and "cut off at the output limit (8192 tokens)" in note["content"]


def test_limit_is_capped_and_continues_are_limited():
    client = LimitClient(cut=10)
    response = make(client, max_tokens=16000).run("implement the cache")
    assert client.limits == [16000, 32000, 32768, 32768][: MAX_LENGTH_CONTINUES + 1]
    assert max(client.limits) <= MAX_OUTPUT_TOKENS
    # After the last continue the cut-off text is returned rather than looping
    assert response.text == "Let me think about the design..."


def test_refused_higher_limit_falls_back_to_the_configured_one():
    client = LimitClient(cut=1, refuse_above=8192)
    response = make(client).run("implement the cache")
    assert response.text == "Done."
    assert client.limits == [8192, 8192]
