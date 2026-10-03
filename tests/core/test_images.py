"""Tests for attaching images to requests."""

import base64
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from joshu.core import images as images_module
from joshu.core.agent import Agent
from joshu.core.compaction import _render_transcript, estimate_tokens
from joshu.core.images import (
    ImageError,
    build_user_content,
    find_image_refs,
    image_part,
    message_text,
)
from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import PermissionManager
from joshu.core.sessions import load_session

# A valid 1x1 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=="
)


@pytest.fixture
def shot(tmp_path):
    path = tmp_path / "shot.png"
    path.write_bytes(PNG)
    return path


class FakeClient:
    model = "fake"

    def __init__(self):
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append([dict(m) for m in messages])
        return AssistantTurn(content="I see a pixel.")


def test_image_part_is_a_data_url(shot):
    part = image_part(shot)
    assert part["type"] == "image_url"
    url = part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == PNG


@pytest.mark.parametrize(
    "name,content,message",
    [
        ("notes.bmp", b"x", "unsupported image type"),
        ("missing.png", None, "Image not found"),
    ],
)
def test_invalid_images_are_rejected(tmp_path, name, content, message):
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(ImageError, match=message):
        image_part(path)


def test_size_limit(shot, monkeypatch):
    monkeypatch.setattr(images_module, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(ImageError, match="at most"):
        image_part(shot)


def test_find_image_refs_only_takes_existing_images(shot, tmp_path):
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    text, paths = find_image_refs(
        "What is in @shot.png? Compare with @missing.png and @notes.txt, mail me@host.png",
        cwd=tmp_path,
    )
    assert paths == [tmp_path / "shot.png"]
    assert text == (
        "What is in [image: shot.png]? Compare with @missing.png and @notes.txt, mail me@host.png"
    )


def test_message_text_and_build_user_content(shot):
    assert build_user_content("hi") == "hi"
    content = build_user_content("describe", [shot])
    assert content[0] == {"type": "text", "text": "describe"}
    assert message_text(content) == "describe\n[image]"


def test_agent_sends_image_parts(shot, tmp_path):
    client = FakeClient()
    agent = Agent(client=client, permissions=PermissionManager(), system_prompt="s", cwd=tmp_path)
    agent.run("what is this?", images=[shot])

    user = client.requests[0][-1]
    assert user["role"] == "user"
    assert user["content"][0]["text"] == "what is this?"
    assert user["content"][1]["type"] == "image_url"


def test_images_are_estimated_not_counted_by_base64_size(tmp_path):
    big = tmp_path / "big.png"
    big.write_bytes(b"\x89PNG" + b"0" * 2_000_000)
    message = {"role": "user", "content": build_user_content("look", [big])}
    assert estimate_tokens([message]) < 10_000
    assert "[image]" in _render_transcript([message])


def test_saved_session_title_is_the_text(shot, tmp_path):
    agent = Agent(
        client=FakeClient(),
        permissions=PermissionManager(),
        system_prompt="s",
        cwd=tmp_path,
        persist=True,
    )
    agent.run("describe this screenshot", images=[shot])
    assert load_session(agent.session_id)["title"] == "describe this screenshot [image]"


def test_cli_attaches_referenced_and_option_images(shot, tmp_path, monkeypatch):
    from joshu.ui.cli import app

    monkeypatch.chdir(tmp_path)
    other = tmp_path / "other.jpg"
    other.write_bytes(PNG)
    client = FakeClient()
    with patch("joshu.core.agent.create_chat_client", return_value=client):
        result = CliRunner().invoke(
            app, ["run", "-p", "--image", str(other), "compare @shot.png with the other one"]
        )

    assert result.exit_code == 0, result.output
    parts = client.requests[0][-1]["content"]
    assert parts[0]["text"] == "compare [image: shot.png] with the other one"
    urls = [p["image_url"]["url"] for p in parts[1:]]
    assert urls[0].startswith("data:image/jpeg") and urls[1].startswith("data:image/png")


def test_cli_rejects_missing_image_before_calling_the_model(tmp_path, monkeypatch):
    from joshu.ui.cli import app

    monkeypatch.chdir(tmp_path)
    client = FakeClient()
    with patch("joshu.core.agent.create_chat_client", return_value=client):
        result = CliRunner().invoke(app, ["run", "-p", "--image", "nope.png", "look"])

    assert result.exit_code == 2
    assert client.requests == []


def test_interactive_routes_image_refs_to_the_agent(shot, tmp_path, monkeypatch):
    from joshu.ui.interactive.interactive_mode import InteractiveMode

    monkeypatch.chdir(tmp_path)
    assert InteractiveMode._references_image("@shot.png what is this")
    assert not InteractiveMode._references_image("@notes.txt")
    assert json.dumps(find_image_refs("@shot.png", tmp_path)[0]) == '"[image: shot.png]"'
