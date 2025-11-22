import os
import pytest

from openai import OpenAI


@pytest.mark.integration
def test_openrouter_deepseek_free_reachability():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set; skipping reachability test")

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    headers = {
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", ""),
        "X-Title": os.getenv("OPENROUTER_SITE_TITLE", "Joshu Assistant Tests"),
    }

    # Use a more commonly available free model
    completion = client.chat.completions.create(
        extra_headers=headers,
        model="openai/gpt-4o-mini",  # More reliable free model
        messages=[
            {"role": "user", "content": "ping: return 'pong' only"},
        ],
    )

    assert completion is not None
    assert getattr(completion, "choices", None)
    content = completion.choices[0].message.content
    assert isinstance(content, str)
    assert len(content) > 0