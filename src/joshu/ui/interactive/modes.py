"""Mode handlers for interactive mode (agent, ask, plan)."""

import json
import os
import re
import time
from typing import Dict, List

from joshu.core.safety import assess_command_safety
from joshu.core.translate import _is_conversational_query
from joshu.tools.shell import run_command


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


class AgentModeHandler(ModeHandler):
    """Handler for agent mode - autonomous task execution."""

    def handle(self, user_input: str) -> bool:
        """Handle agent mode input."""
        try:
            # Check if conversational query
            if _is_conversational_query(user_input):
                response_lines = [
                    "💬 I see you're saying hello! In agent mode, I execute tasks from start to finish.",
                    "",
                    "For conversations, use /ask mode. For task planning, use /plan mode.",
                    "",
                    "But I can still help! What task would you like me to execute? (e.g., 'create a Python project')",
                ]
                formatted_response = "\n".join(response_lines)
                for line in response_lines:
                    self._show_message(line if line else "")

                if self.context_provider:
                    self.context_provider.add_to_history(
                        "assistant",
                        formatted_response,
                        metadata={
                            "mode": "agent",
                            "conversational": True,
                            "timestamp": time.time(),
                        },
                    )
                return True

            # Generate plan
            goal_message = f"🎯 Goal: {user_input}"
            planning_message = "📝 Generating execution plan...\n"
            self._show_message(f"\n{goal_message}")
            self._show_message(planning_message)

            context_messages = []
            if self.context_provider:
                context_messages = self.context_provider.get_relevant_context(
                    user_input, max_tokens=3000
                )

            plan_prompt = f"""Break down the following goal into a sequential list of shell commands to achieve it.
Return the commands as a JSON array of strings. Each command should be executable on {os.name} system.
Goal: '{user_input}'

Return ONLY a JSON array, for example: ["mkdir project", "cd project", "echo 'Hello' > file.txt"]
Do not include any explanation or markdown formatting, just the JSON array."""

            plan_response = self._get_llm_response(
                "You are a task planner that generates executable shell commands as JSON arrays.",
                plan_prompt,
                context_messages,
                temperature=0.3,
                max_tokens=1024,
            )

            if not plan_response:
                self._show_message(
                    "❌ Unable to generate plan. Please check your model configuration."
                )
                return True

            # Parse JSON commands
            commands = self._parse_plan_response(plan_response)
            if not commands:
                return True

            # Execute commands
            return self._execute_plan(commands, goal_message, planning_message, user_input)

        except KeyboardInterrupt:
            self._show_message("\n⏹️  Execution interrupted by user.")
            return True
        except Exception as e:
            self._show_message(f"❌ Error in agent mode: {str(e)}")
            import traceback

            self._show_message(traceback.format_exc())
            return True

    def _parse_plan_response(self, plan_response: str) -> List[str]:
        """Parse JSON array from plan response."""
        try:
            cleaned_response = plan_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            json_match = re.search(r"\[[\s\S]*\]", cleaned_response)
            if json_match:
                commands = json.loads(json_match.group())
            else:
                commands = json.loads(cleaned_response)

            if not isinstance(commands, list):
                self._show_message("❌ Invalid plan format. Expected a list of commands.")
                return []

            return [str(cmd).strip() for cmd in commands if cmd]
        except (json.JSONDecodeError, ValueError) as e:
            self._show_message(f"❌ Failed to parse plan: {str(e)}")
            self._show_message(f"Raw response: {plan_response[:200]}...")
            return []

    def _execute_plan(
        self, commands: List[str], goal_message: str, planning_message: str, user_input: str
    ) -> bool:
        """Execute plan step by step."""
        execution_start_message = f"\n🚀 Executing {len(commands)} step(s)...\n"
        self._show_message(execution_start_message)

        executed_count = 0
        failed_count = 0
        execution_log = [
            goal_message,
            planning_message.strip(),
            f"Generated plan with {len(commands)} command(s)",
            execution_start_message.strip(),
        ]

        for i, command in enumerate(commands, 1):
            step_message = f"[Step {i}/{len(commands)}] Running: {command}"
            self._show_message(step_message)
            execution_log.append(step_message)

            # Safety check
            report = assess_command_safety(command, self.sandbox)
            if not report.safe:
                self._show_message(f"⚠️  WARNING: Command flagged as {report.danger_level}")
                for reason in report.reasons:
                    self._show_message(f"  - {reason}")

                try:
                    confirm = input("Continue anyway? [y/N]: ").strip().lower()
                    if confirm not in ["y", "yes"]:
                        self._show_message("⏭️  Skipping this step.")
                        continue
                except (EOFError, KeyboardInterrupt):
                    self._show_message("\n⏹️  Execution stopped by user.")
                    break

            # Execute command
            code, out, err = run_command(command)

            if out:
                self._show_message(out)
                execution_log.append(f"Output: {out[:200]}")
            if err:
                error_msg = f"⚠️  {err}"
                self._show_message(error_msg)
                execution_log.append(error_msg)

            if code != 0:
                failure_msg = f"❌ Command failed with exit code {code}"
                self._show_message(failure_msg)
                execution_log.append(failure_msg)
                failed_count += 1

                try:
                    continue_execution = input("Continue with next step? [y/N]: ").strip().lower()
                    if continue_execution not in ["y", "yes"]:
                        self._show_message("⏹️  Execution stopped.")
                        break
                except (EOFError, KeyboardInterrupt):
                    self._show_message("\n⏹️  Execution stopped by user.")
                    break
            else:
                executed_count += 1

            # Store in memory
            if self.context_provider:
                result = f"Command: {command}\nExit code: {code}\nOutput: {out[:500] if out else 'No output'}\nError: {err[:500] if err else 'No errors'}"
                self.context_provider.set_memory(f"last_command_{i}", result)

        # Final summary
        summary_header = "=" * 50
        summary_title = "📊 Execution Summary:"
        success_msg = f"  ✅ Successfully executed: {executed_count}/{len(commands)}"

        self._show_message("\n" + summary_header)
        self._show_message(summary_title)
        self._show_message(success_msg)
        if failed_count > 0:
            failure_summary = f"  ❌ Failed: {failed_count}/{len(commands)}"
            self._show_message(failure_summary)
            execution_log.append(failure_summary)
        self._show_message(summary_header + "\n")

        execution_log.extend([summary_header, summary_title, success_msg])
        if failed_count > 0:
            execution_log.append(f"  ❌ Failed: {failed_count}/{len(commands)}")
        execution_log.append(summary_header)

        complete_response = "\n".join(execution_log)
        if self.context_provider:
            self.context_provider.add_to_history(
                "assistant",
                complete_response,
                metadata={
                    "mode": "agent",
                    "goal": user_input,
                    "commands_executed": executed_count,
                    "commands_total": len(commands),
                    "failed_count": failed_count,
                    "timestamp": time.time(),
                },
            )

        return True
