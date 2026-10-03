"""Mode handlers for interactive ask mode and the plan-mode fallback.

Agent and plan modes normally run the tool-using agent (joshu.core.agent); the plan
handler here is used only when no model endpoint supports it.
"""

import os
import time
from typing import Dict, List


class ModeHandler:
    """Base class for mode handlers."""

    def __init__(self, interactive_mode):
        self.interactive_mode = interactive_mode
        self.model = interactive_mode.model
        self.sandbox = interactive_mode.sandbox
        self.context_provider = interactive_mode.context_provider
        self.config_manager = interactive_mode.config_manager

    def _get_llm_response(
        self,
        system_prompt: str,
        user_prompt: str,
        context_messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Get LLM response using OpenRouter or local model."""
        from joshu.models.openrouter import chat_completion

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        model_specific_keys = [
            "DEEPSEEK_API_KEY",
            "TONGYI_API_KEY",
            "QWEN_API_KEY",
            "KIMI_DEV_API_KEY",
            "AGENTICAT_API_KEY",
            "GLM_API_KEY",
        ]
        has_model_key = any(os.getenv(key) for key in model_specific_keys)
        use_cloud_env = os.getenv("JOSHU_USE_CLOUD", "").lower()
        use_cloud = (use_cloud_env == "true") or (
            use_cloud_env == "" and (openrouter_key or has_model_key)
        )

        if (openrouter_key or has_model_key) and use_cloud:
            model_name = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
            messages = [{"role": "system", "content": system_prompt}]
            for msg in context_messages:
                if msg.get("role") != "user" or msg.get("content") != user_prompt:
                    messages.append(msg)
            messages.append({"role": "user", "content": user_prompt})

            response = chat_completion(
                messages, model=model_name, temperature=temperature, max_tokens=max_tokens
            )
            if response:
                return response

        # Fallback to local model via pool
        from joshu.models.pool import get_model_pool

        pool = get_model_pool()
        available_providers = pool.get_available_providers()
        if available_providers:
            model_provider = available_providers[0]  # Use first available (prioritized)
            context_str = ""
            if context_messages:
                context_str = "\n".join(
                    [f"{msg['role']}: {msg['content'][:200]}" for msg in context_messages[-5:]]
                )
            full_prompt = (
                f"{system_prompt}\n\n{context_str}\n\n{user_prompt}"
                if context_str
                else f"{system_prompt}\n\n{user_prompt}"
            )
            return model_provider.generate(
                full_prompt, temperature=temperature, max_tokens=max_tokens
            )

        return None

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

            system_message = """You are Joshu, an expert AI assistant. Answer the user's questions clearly and concisely.
Do not generate or suggest shell commands. Provide helpful, informative responses based on your knowledge."""

            response = self._get_llm_response(
                system_message, user_input, context_messages, temperature=0.7, max_tokens=1024
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

            self._show_message(
                "Unable to generate response. Please check your model configuration."
            )
            return True
        except Exception as e:
            self._show_message(f"Error in ask mode: {str(e)}")
            return True


class PlanModeHandler(ModeHandler):
    """Handler for plan mode - generate plans without execution."""

    def handle(self, user_input: str) -> bool:
        """Handle plan mode input."""
        try:
            context_messages = []
            if self.context_provider:
                context_messages = self.context_provider.get_relevant_context(
                    user_input, max_tokens=3000
                )

            system_message = """You are a task planner. Break down the user's request into a clear, numbered list of actionable steps.
Each step should be a concise command or action. Format your response as a numbered list with clear, executable steps.
Do not execute any commands - only provide the plan."""

            response = self._get_llm_response(
                system_message, user_input, context_messages, temperature=0.5, max_tokens=1024
            )

            if response:
                plan_message = "\n📋 Plan:"
                formatted_plan = f"{plan_message}\n{response}"
                self._show_message(plan_message)
                self._show_message(response)
                if self.context_provider:
                    self.context_provider.add_to_history(
                        "assistant",
                        formatted_plan,
                        metadata={"mode": "plan", "timestamp": time.time()},
                    )
                return True

            self._show_message("Unable to generate plan. Please check your model configuration.")
            return True
        except Exception as e:
            self._show_message(f"Error in plan mode: {str(e)}")
            return True
