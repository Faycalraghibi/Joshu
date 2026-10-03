"""Ask mode for interactive sessions: direct answers without tools.

Agent and plan modes run the tool-using agent (joshu.core.agent).
"""

import time
from typing import Dict, List, Optional

ASK_SYSTEM_PROMPT = """You are Joshu, an expert AI assistant. Answer the user's questions clearly and concisely.
Do not generate or suggest shell commands. Provide helpful, informative responses based on your knowledge."""


class ModeHandler:
    """Base class for mode handlers."""

    def __init__(self, interactive_mode):
        self.interactive_mode = interactive_mode
        self.model = interactive_mode.model
        self.sandbox = interactive_mode.sandbox
        self.context_provider = interactive_mode.context_provider
        self.config_manager = interactive_mode.config_manager
        self._client = None

    def _get_llm_response(
        self,
        system_prompt: str,
        user_prompt: str,
        context_messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Optional[str]:
        """
        Get a plain-text answer from the configured provider.

        Raises:
            LLMError: when no provider is configured or the request fails.
        """
        from joshu.core.llm_client import create_chat_client

        if self._client is None:
            self._client = create_chat_client(self.model)

        messages = [{"role": "system", "content": system_prompt}]
        for msg in context_messages:
            if msg.get("role") in ("user", "assistant") and msg.get("content") != user_prompt:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_prompt})

        turn = self._client.complete(
            messages, tools=None, max_tokens=max_tokens, temperature=temperature
        )
        return turn.content or None

    def _show_message(self, message: str):
        """Show message through interactive mode."""
        self.interactive_mode._show_message(message)


class AskModeHandler(ModeHandler):
    """Handler for ask mode - direct Q&A without commands."""

    def handle(self, user_input: str) -> bool:
        """Handle ask mode input."""
        try:
            context_messages = []
            if self.context_provider:
                context_messages = self.context_provider.get_relevant_context(
                    user_input, max_tokens=3000
                )

            response = self._get_llm_response(
                ASK_SYSTEM_PROMPT, user_input, context_messages, temperature=0.7, max_tokens=1024
            )

            if response:
                formatted_response = f"💬 {response}"
                self._show_message(formatted_response)
                if self.context_provider:
                    self.context_provider.add_to_history(
                        "assistant",
                        formatted_response,
                        metadata={"mode": "ask", "timestamp": time.time()},
                    )
                return True

            self._show_message("The model returned an empty answer.")
            return True
        except Exception as e:
            self._show_message(f"Error in ask mode: {str(e)}")
            return True
