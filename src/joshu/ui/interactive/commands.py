"""Command handlers for interactive mode slash commands."""

import json

from joshu.ui.interactive.commands_extra import ExtraCommands

INIT_PROMPT = """Create or update AGENTS.md at the root of this repository: instructions for AI coding agents working here.

First explore: the README, build and dependency files (pyproject.toml, package.json, Makefile, ...), CI configuration, the source layout and a few representative files. Then write a concise AGENTS.md (under about 150 lines) covering:
- What the project is, in two or three sentences
- How to install dependencies, build, run the tests (including a single test) and lint
- The layout: main directories and what lives where
- Conventions that aren't obvious from the code: style, naming, patterns to follow, things to avoid
- Anything a newcomer would likely get wrong

Only include facts you verified in the repository; don't invent commands. If AGENTS.md (or JOSHU.md / CLAUDE.md) already exists, read it and improve it rather than starting over, keeping what is still accurate."""


def _shorten(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class CommandHandler(ExtraCommands):
    """Handler for slash commands."""

    def __init__(self, interactive_mode):
        self.interactive_mode = interactive_mode
        self.context_provider = interactive_mode.context_provider
        self.config_manager = interactive_mode.config_manager

    def handle_session_command(self, command: str) -> bool:
        """
        Agent sessions: /session [list | new | switch <id> | delete <id> | help].

        Sessions are the saved agent conversations (see joshu.core.sessions),
        the same ones `joshu sessions`, --resume and /resume use.
        """
        from pathlib import Path

        from joshu.core.sessions import SessionError, delete_session, list_sessions

        show = self.interactive_mode._show_message
        parts = command.split()
        subcommand = parts[1].lower() if len(parts) > 1 else ""
        agent = self.interactive_mode.agent

        if subcommand == "":
            if agent is None:
                show("No agent session yet; it starts with your first request.")
            else:
                show(f"Current session: {agent.session_id}")
            return True

        if subcommand == "help":
            show(
                "Session commands:\n"
                "  /session              - Show the current session\n"
                "  /session list         - Saved sessions in this directory\n"
                "  /session new          - Start a new conversation (also /reset, /new-session)\n"
                "  /session switch <id>  - Continue a saved session (also /resume <id>)\n"
                "  /session delete <id>  - Delete a saved session\n"
                "An id prefix is enough."
            )
            return True

        if subcommand == "list":
            infos = list_sessions(Path.cwd(), limit=20)
            if not infos:
                show("No saved sessions in this directory.")
                return True
            current = agent.session_id if agent is not None else None
            lines = ["Saved sessions (newest first):"]
            for info in infos:
                marker = "*" if info.id == current else " "
                updated = info.updated_at.replace("T", " ")
                lines.append(
                    f" {marker} {info.id}  {updated}  {info.message_count:>3} msgs  "
                    f"{info.title[:60]}"
                )
            show("\n".join(lines))
            return True

        if subcommand in ("new", "end"):
            if agent is not None:
                agent.reset()
                show(f"New session: {agent.session_id}")
            else:
                show("A new session starts with your next request.")
            return True

        if subcommand == "switch":
            if len(parts) < 3:
                show("Usage: /session switch <id>   (see /session list)")
                return True
            self.interactive_mode.resume_session(parts[2])
            return True

        if subcommand == "delete":
            if len(parts) < 3:
                show("Usage: /session delete <id>   (see /session list)")
                return True
            if agent is not None and agent.session_id.startswith(parts[2]):
                show("That is the current session; start a new one first (/session new).")
                return True
            try:
                deleted = delete_session(parts[2])
            except SessionError as e:
                show(str(e))
                return True
            show(f"Deleted session {deleted}")
            return True

        show(f"Unknown session command: {subcommand} (see /session help)")
        return True

    def handle_auto_memory_command(self, command: str) -> bool:
        """/memory [list] and /memory forget <name> [user]: the agent's saved memories."""
        from joshu.core.auto_memory import delete_memory, list_memories, memory_dir

        parts = command.split()
        if len(parts) >= 3 and parts[1] == "forget":
            scope = "user" if len(parts) > 3 and parts[3] == "user" else "project"
            if delete_memory(parts[2], scope):
                self.interactive_mode._show_message(f"Forgot {scope} memory '{parts[2]}'.")
            else:
                self.interactive_mode._show_message(f"No {scope} memory named '{parts[2]}'.")
            return True

        lines = []
        for scope, title in (("project", "Project memory"), ("user", "User memory")):
            memories = list_memories(scope)
            lines.append(f"{title} ({memory_dir(scope)}):")
            if not memories:
                lines.append("  (none)")
            for m in memories:
                lines.append(f"  {m.name:<24} [{m.type}] {m.description}")
        lines += [
            "",
            "The agent saves these as it learns; edit the files directly or:",
            "  /memory forget <name> [user]  - Delete a memory",
            "  /memory status | search <q> | clear - Semantic memory of past conversations",
        ]
        self.interactive_mode._show_message("\n".join(lines))
        return True

    def handle_memory_command(self, command: str) -> bool:
        """Handle memory commands: saved memories, then semantic memory."""
        parts = command.split()
        if len(parts) == 1 or parts[1] in ("list", "forget"):
            return self.handle_auto_memory_command(command)
        if not self.context_provider:
            self.interactive_mode._show_message("❌ Context provider not available.")
            return True

        if not hasattr(self.context_provider, "semantic_memory"):
            self.interactive_mode._show_message("❌ Semantic memory not available.")
            return True

        semantic_memory = self.context_provider.semantic_memory

        parts = command.split(maxsplit=2)

        if len(parts) == 1:
            self.interactive_mode._show_message("📚 Semantic Memory Commands:")
            self.interactive_mode._show_message("")
            self.interactive_mode._show_message(
                "  /memory status          - Show memory statistics"
            )
            self.interactive_mode._show_message(
                "  /memory search <query>  - Search for similar past conversations"
            )
            self.interactive_mode._show_message(
                "  /memory clear           - Clear all semantic memories"
            )
            self.interactive_mode._show_message("")
            self.interactive_mode._show_message(
                "💡 Semantic memory allows Joshu to recall relevant past conversations"
            )
            self.interactive_mode._show_message("   based on meaning, not just recency.")
            return True

        subcommand = parts[1].lower()

        if subcommand == "status":
            if not semantic_memory.enabled:
                self.interactive_mode._show_message(
                    "⚠️  Semantic memory is disabled (missing dependencies)"
                )
                self.interactive_mode._show_message("💡 Install with: pip install -e .[semantic]")
                return True

            count = semantic_memory.count()
            self.interactive_mode._show_message("📊 Semantic Memory Status:")
            self.interactive_mode._show_message("")
            self.interactive_mode._show_message("  Status: ✅ Enabled")
            self.interactive_mode._show_message(f"  Total memories: {count}")
            self.interactive_mode._show_message("  Embedding model: all-MiniLM-L6-v2")
            self.interactive_mode._show_message("  Storage: ChromaDB (persistent)")
            self.interactive_mode._show_message("")

            if hasattr(self.config_manager, "config"):
                config = self.config_manager.config
                threshold = getattr(config, "semantic_memory_similarity_threshold", 0.3)
                max_results = getattr(config, "semantic_memory_max_results", 5)
                min_length = getattr(config, "semantic_memory_min_content_length", 10)

                self.interactive_mode._show_message("  Configuration:")
                self.interactive_mode._show_message(f"    - Similarity threshold: {threshold}")
                self.interactive_mode._show_message(f"    - Max results: {max_results}")
                self.interactive_mode._show_message(f"    - Min content length: {min_length}")

            return True

        elif subcommand == "search":
            if not semantic_memory.enabled:
                self.interactive_mode._show_message(
                    "⚠️  Semantic memory is disabled (missing dependencies)"
                )
                return True

            if len(parts) < 3:
                self.interactive_mode._show_message("❌ Usage: /memory search <query>")
                self.interactive_mode._show_message(
                    "💡 Example: /memory search python machine learning"
                )
                return True

            query = parts[2]

            max_results = 5
            min_score = 0.3
            if hasattr(self.config_manager, "config"):
                config = self.config_manager.config
                max_results = getattr(config, "semantic_memory_max_results", 5)
                min_score = getattr(config, "semantic_memory_similarity_threshold", 0.3)

            results = semantic_memory.search(query=query, limit=max_results, min_score=min_score)

            if not results:
                self.interactive_mode._show_message(f"🔍 No relevant memories found for: '{query}'")
                self.interactive_mode._show_message(
                    "💡 Try a different query or lower the similarity threshold"
                )
                return True

            self.interactive_mode._show_message(
                f"🔍 Found {len(results)} relevant memories for: '{query}'"
            )
            self.interactive_mode._show_message("")

            for i, entry in enumerate(results, 1):
                from datetime import datetime

                timestamp_str = "Unknown"
                if entry.timestamp:
                    try:
                        dt = datetime.fromtimestamp(entry.timestamp)
                        timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                session_info = ""
                if entry.session_id:
                    session_info = f" [Session: {entry.session_id[:8]}...]"

                self.interactive_mode._show_message(
                    f"{i}. [{entry.role.upper()}]{session_info} @ {timestamp_str}"
                )

                content = entry.content
                if len(content) > 200:
                    content = content[:197] + "..."

                self.interactive_mode._show_message(f"   {content}")
                self.interactive_mode._show_message("")

            return True

        elif subcommand == "clear":
            if not semantic_memory.enabled:
                self.interactive_mode._show_message(
                    "⚠️  Semantic memory is disabled (missing dependencies)"
                )
                return True

            count = semantic_memory.count()

            if count == 0:
                self.interactive_mode._show_message("ℹ️  No memories to clear.")
                return True

            success = semantic_memory.clear()

            if success:
                self.interactive_mode._show_message(f"✅ Cleared {count} semantic memories.")
                self.interactive_mode._show_message(
                    "💡 New conversations will continue to be stored automatically."
                )
            else:
                self.interactive_mode._show_message("❌ Failed to clear semantic memories.")

            return True

        else:
            self.interactive_mode._show_message(f"❌ Unknown memory command: {subcommand}")
            self.interactive_mode._show_message("💡 Available commands: status, search, clear")
            self.interactive_mode._show_message("💡 Type '/memory' for detailed information")
            return True

    def handle_slash_command(self, command: str) -> bool:
        """Run a slash command. Returns False when the session should end (/exit)."""
        from joshu.ui.interactive.command_registry import find_command

        name, _, arg = command.strip().partition(" ")
        spec = find_command(name)
        if spec is None:
            return self.handle_custom_command(command)
        result = getattr(self, spec.method)(arg.strip())
        return True if result is None else bool(result)

    # Adapters from the registry to the handlers below

    def cmd_clear(self, arg: str = "") -> bool:
        return self.handle_session_command("/session new")

    def cmd_compact(self, arg: str = "") -> bool:
        return self.handle_compact_command(f"/compact {arg}".strip())

    def cmd_rewind(self, arg: str = "") -> bool:
        return self.handle_rewind_command(f"/rewind {arg}".strip())

    def cmd_undo(self, arg: str = "") -> bool:
        return self.handle_undo_command()

    def cmd_resume(self, arg: str = "") -> bool:
        return self.handle_resume_command(f"/resume {arg}".strip())

    def cmd_session(self, arg: str = "") -> bool:
        return self.handle_session_command(f"/session {arg}".strip())

    def cmd_cost(self, arg: str = "") -> bool:
        return self.handle_cost_command()

    def cmd_memory(self, arg: str = "") -> bool:
        return self.handle_memory_command(f"/memory {arg}".strip())

    def cmd_init(self, arg: str = "") -> bool:
        return self.handle_init_command(f"/init {arg}".strip())

    def cmd_model(self, arg: str = "") -> bool:
        self.handle_model_command(f"/model {arg}".strip())
        return True

    def cmd_models(self, arg: str = "") -> bool:
        return self.handle_models_list(f"/models {arg}".strip())

    def cmd_permissions(self, arg: str = "") -> bool:
        return self.handle_permissions_command(f"/permissions {arg}".strip())

    def cmd_config(self, arg: str = "") -> bool:
        self.handle_config_command(f"/config {arg}".strip())
        return True

    def cmd_skills(self, arg: str = "") -> bool:
        return self.handle_skills_list()

    def cmd_agents(self, arg: str = "") -> bool:
        return self.handle_agents_list()

    def cmd_commands(self, arg: str = "") -> bool:
        return self.handle_commands_list()

    def cmd_help(self, arg: str = "") -> bool:
        self.show_help()
        return True

    def cmd_exit(self, arg: str = "") -> bool:
        return False

    def cmd_history(self, arg: str = "") -> bool:
        if arg == "clear":
            self.interactive_mode.prompt_history.clear()
            self.interactive_mode.command_history = []
            self.interactive_mode._show_message("Input history cleared.")
        else:
            self.display_history()
        return True

    def cmd_search(self, arg: str = "") -> bool:
        if not arg:
            self.interactive_mode._show_message("Usage: /search <query>")
            return True
        from joshu.ui.cli_handlers.search_handler import handle_search_command

        handle_search_command(arg, max_results=None)
        return True

    def cmd_agent(self, arg: str = "") -> bool:
        self.interactive_mode.interaction_mode = "agent"
        self.interactive_mode._show_message(
            "Agent mode: I read, edit and run commands to finish tasks, asking before edits "
            "and shell commands."
        )
        return True

    def cmd_ask(self, arg: str = "") -> bool:
        self.interactive_mode.interaction_mode = "ask"
        self.interactive_mode._show_message("Ask mode: I answer directly, without using tools.")
        return True

    def cmd_plan(self, arg: str = "") -> bool:
        self.interactive_mode.interaction_mode = "plan"
        self.interactive_mode._show_message(
            "Plan mode: I investigate with read-only tools and propose a plan without "
            "changing anything."
        )
        return True

    def handle_custom_command(self, command: str) -> bool:
        """Run a custom command from .joshu/commands or ~/.joshu/commands."""
        from joshu.core.custom_commands import discover_commands, split_command

        parsed = split_command(command)
        if parsed is not None and parsed[0] in discover_commands():
            return self.interactive_mode.run_custom_command(command)
        if parsed is not None and self.run_skill(parsed[0], parsed[1]):
            return True
        self.interactive_mode._show_message(
            f"Unknown command: {command.split()[0]} (see /help, /commands and /skills)"
        )
        return True

    def run_skill(self, name: str, request: str) -> bool:
        """/<skill> [request]: run the agent with that skill. False if no such skill."""
        from joshu.core.skills import discover_skills

        if name not in discover_skills():
            return False
        if not self.interactive_mode._ensure_agent():
            return True
        prompt = f"Use the {name} skill: load it with the skill tool, then follow it."
        if request.strip():
            prompt += f"\n\n{request.strip()}"
        self.interactive_mode._run_agent(prompt)
        return True

    def handle_skills_list(self) -> bool:
        """List available skills."""
        from joshu.core.skills import discover_skills, skill_dirs

        skills = discover_skills()
        if not skills:
            dirs = ", ".join(str(d) for d, _ in skill_dirs())
            self.interactive_mode._show_message(
                f"No skills. Add <name>/SKILL.md (with a name and description) to one of: {dirs}"
            )
            return True
        lines = ["Skills (the agent loads one when a task matches; /<name> runs it):"]
        for name, skill in sorted(skills.items()):
            lines.append(f"  /{name:<16} {skill.description}  [{skill.scope}]")
        self.interactive_mode._show_message("\n".join(lines))
        return True

    def handle_agents_list(self) -> bool:
        """List user-defined sub-agents."""
        from joshu.core.subagents import agent_dirs, discover_subagents

        specs = discover_subagents()
        if not specs:
            dirs = " or ".join(str(d) for d in reversed(agent_dirs()))
            self.interactive_mode._show_message(f"No sub-agents defined. Add .md files to {dirs}.")
            return True
        lines = ["Sub-agents (the agent delegates to them with its task tool):"]
        for name, spec in sorted(specs.items()):
            tools = ", ".join(spec.tools) if spec.tools else "read-only"
            lines.append(f"  {name:<16} {spec.description}  [tools: {tools}]")
        self.interactive_mode._show_message("\n".join(lines))
        return True

    def handle_commands_list(self) -> bool:
        """List custom commands."""
        from joshu.core.custom_commands import command_dirs, discover_commands

        commands = discover_commands()
        if not commands:
            dirs = " or ".join(str(d) for d in reversed(command_dirs()))
            self.interactive_mode._show_message(
                f"No custom commands. Add .md or .toml files to {dirs}."
            )
            return True
        lines = ["Custom commands:"]
        for name, cmd in sorted(commands.items()):
            lines.append(f"  /{name:<16} {cmd.description}")
        self.interactive_mode._show_message("\n".join(lines))
        return True

    def handle_resume_command(self, command: str) -> bool:
        """/resume lists recent sessions here; /resume <id> continues one."""
        from pathlib import Path

        from joshu.core.sessions import list_sessions

        parts = command.split(maxsplit=1)
        if len(parts) == 2:
            self.interactive_mode.resume_session(parts[1].strip())
            return True

        infos = list_sessions(Path.cwd(), limit=10)
        if not infos:
            self.interactive_mode._show_message("No saved sessions in this directory.")
            return True
        lines = ["Recent sessions (resume with /resume <id>):"]
        for info in infos:
            updated = info.updated_at.replace("T", " ")
            lines.append(f"  {info.id}  {updated}  {info.message_count:>3} msgs  {info.title[:60]}")
        self.interactive_mode._show_message("\n".join(lines))
        return True

    def handle_cost_command(self) -> bool:
        """Tokens and cost of the current agent conversation."""
        from joshu.core.costs import format_cost

        agent = self.interactive_mode.agent
        if agent is None:
            self.interactive_mode._show_message("No agent conversation yet.")
            return True
        usage = agent.usage
        self.interactive_mode._show_message(
            f"Session {agent.session_id} ({getattr(agent.client, 'model', '?')}):\n"
            f"  input tokens:  {usage['prompt_tokens']:,}"
            f" ({usage.get('cached_tokens', 0):,} from cache)\n"
            f"  output tokens: {usage['completion_tokens']:,}\n"
            f"  cost:          {format_cost(agent.cost)}"
        )
        return True

    def handle_undo_command(self) -> bool:
        """Revert the agent's file edits from its most recent request that edited files."""
        agent = self.interactive_mode.agent
        checkpoint = agent.undo() if agent is not None else None
        if checkpoint is None:
            self.interactive_mode._show_message("Nothing to undo.")
            return True

        lines = [f"Undid file changes for: {checkpoint.prompt}"]
        for path, original in checkpoint.files.items():
            action = "deleted (was created)" if original is None else "restored"
            lines.append(f"  {agent._display_path(path)} - {action}")
        lines.append("Changes made by shell commands are not undone.")
        self.interactive_mode._show_message("\n".join(lines))
        return True

    def handle_rewind_command(self, command: str) -> bool:
        """/rewind [n]: drop the last n requests and restore the files they changed."""
        agent = self.interactive_mode.agent
        arg = command[len("/rewind") :].strip() or "1"
        if not arg.isdigit() or int(arg) < 1:
            self.interactive_mode._show_message("Usage: /rewind [n]  (n requests, default 1)")
            return True
        rewind = agent.rewind(int(arg)) if agent is not None else None
        if rewind is None:
            self.interactive_mode._show_message("Nothing to rewind.")
            return True

        lines = [f"Rewound {len(rewind.prompts)} request(s):"]
        lines += [f"  - {_shorten(p)}" for p in rewind.prompts]
        if rewind.files:
            lines.append("Restored files:")
            lines += [f"  {agent._display_path(p)}" for p in rewind.files]
        lines.append("Changes made by shell commands are not undone.")
        self.interactive_mode._show_message("\n".join(lines))
        # Offer the first dropped request for editing and resending
        self.interactive_mode.type_ahead = rewind.prompts[0] if rewind.prompts else ""
        return True

    def handle_compact_command(self, command: str) -> bool:
        """/compact [focus]: summarize the conversation now to free context."""
        from joshu.core.llm_client import LLMError

        agent = self.interactive_mode.agent
        if agent is None:
            self.interactive_mode._show_message("Nothing to compact yet.")
            return True
        focus = command[len("/compact") :].strip()
        try:
            result = agent.compact(focus)
        except LLMError as e:
            self.interactive_mode._show_message(f"Model error: {e}")
            return True
        if result is None:
            self.interactive_mode._show_message("Nothing to compact yet.")
        else:
            before, after = result
            self.interactive_mode._show_message(
                f"Compacted the conversation: ~{before:,} -> ~{after:,} tokens."
            )
        return True

    def handle_init_command(self, command: str) -> bool:
        """/init [notes]: have the agent write or update AGENTS.md for this project."""
        notes = command[len("/init") :].strip()
        prompt = INIT_PROMPT + (f"\n\nThe user adds: {notes}" if notes else "")
        if not self.interactive_mode._ensure_agent():
            return True
        return self.interactive_mode._run_agent(prompt)

    def handle_permissions_command(self, command: str) -> bool:
        """Show or set the agent permission mode: /permissions [default|accept_edits|bypass]."""
        from joshu.core.permissions import PermissionMode

        parts = command.split(maxsplit=2)
        if len(parts) == 1:
            current = self.config_manager.get("permission_mode", "default")
            rules = self.config_manager.get("permissions") or {}
            allow = ", ".join(rules.get("allow") or []) or "none"
            deny = ", ".join(rules.get("deny") or []) or "none"
            self.interactive_mode._show_message(
                f"Permission mode: {current}\n"
                "  default      - ask before edits, shell commands and other risky tools\n"
                "  accept_edits - file edits run without asking; shell still asks\n"
                "  bypass       - everything runs; commands flagged unsafe still ask\n"
                "Use /plan for read-only mode.\n"
                f"Saved rules: allow {allow}; deny {deny}\n"
                "Add one: /permissions allow run_shell_command(git status*)\n"
                "         /permissions deny write_file(.env*)"
            )
            return True

        if parts[1] in ("allow", "deny"):
            return self._add_permission_rule(parts[1], parts[2] if len(parts) > 2 else "")

        try:
            mode = PermissionMode.from_string(parts[1])
        except ValueError as e:
            self.interactive_mode._show_message(str(e))
            return True
        if mode == PermissionMode.PLAN:
            self.interactive_mode._show_message("Use /plan to switch to read-only plan mode.")
            return True

        self.config_manager.set("permission_mode", mode.value)
        agent = self.interactive_mode.agent
        if agent is not None and self.interactive_mode.interaction_mode != "plan":
            agent.set_mode(mode)
        self.interactive_mode._show_message(f"Permission mode set to {mode.value}.")
        return True

    def _add_permission_rule(self, kind: str, text: str) -> bool:
        """Save an allow/deny rule to the user config and apply it now."""
        from joshu.core.permissions import PermissionRule, PermissionRules

        show = self.interactive_mode._show_message
        try:
            rule = PermissionRule.parse(text)
        except ValueError as e:
            show(str(e))
            return True

        rules = dict(self.config_manager.get("permissions") or {})
        entries = list(rules.get(kind) or [])
        if str(rule) not in entries:
            entries.append(str(rule))
        rules[kind] = entries
        self.config_manager.set("permissions", rules)
        self.config_manager.save_config()

        agent = self.interactive_mode.agent
        if agent is not None:
            agent.permissions.rules = PermissionRules.from_config(rules)
        show(f"Saved: {kind} {rule}")
        return True

    def display_history(self):
        """Display command history."""
        history_strings = self.interactive_mode.prompt_history.load_history_strings()

        if not history_strings:
            self.interactive_mode._show_message("No command history")
            return

        self.interactive_mode._show_message("Command History:")
        for i, cmd in enumerate(history_strings[-20:], 1):
            self.interactive_mode._show_message(f"{i}: {cmd}")

    def handle_config_command(self, command: str):
        """Handle configuration commands."""
        parts = command.split()
        if len(parts) == 1:
            config_dict = self.config_manager.config.to_dict()
            config_str = json.dumps(config_dict, indent=2)
            self.interactive_mode._show_message(config_str)
        elif len(parts) == 2:
            key = parts[1]
            value = self.config_manager.get(key)
            self.interactive_mode._show_message(f"{key}: {value}")
        elif len(parts) == 3:
            key, value = parts[1], parts[2]
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "").isdigit():
                value = float(value)

            if self.config_manager.set(key, value):
                self.config_manager.save_config()
                self.interactive_mode._show_message(f"Set {key} = {value}")
            else:
                self.interactive_mode._show_message(
                    f"Invalid configuration key or value type: {key}={value!r}"
                )

    def handle_model_command(self, command: str):
        """
        /model shows the model in use; /model <id-or-name> switches this
        conversation to it (joshu use <model> makes it the default).
        """
        from joshu.core.llm_client import LLMError, create_chat_client

        show = self.interactive_mode._show_message
        parts = command.split(maxsplit=1)
        agent = self.interactive_mode.agent
        if len(parts) == 1:
            current = getattr(agent.client, "model", None) if agent else None
            show(f"Model: {current or self.config_manager.get('model')}")
            show("Switch: /model <id or named model>   List: /models [search]")
            return

        model = parts[1].strip()
        try:
            client = create_chat_client(model)
        except LLMError as e:
            show(f"Can't use {model}: {e}")
            return

        self.interactive_mode.model = model
        if agent is not None:
            agent.client = client
            window = getattr(client, "context_window", None)
            if window:
                agent.context_window = window
        show(f"Switched to {client.model} for this conversation (joshu use {model} to keep it).")

    def handle_models_list(self, command: str) -> bool:
        """/models [search]: models the configured provider serves."""
        from joshu.core.model_catalog import CatalogError, filter_models, list_models
        from joshu.core.providers import DEFAULT_PROVIDER, ProviderError, get_providers

        show = self.interactive_mode._show_message
        search = command[len("/models") :].strip() or None
        name = self.config_manager.get("provider") or DEFAULT_PROVIDER
        try:
            provider = get_providers(self.config_manager.get("providers") or {})[name]
            models = filter_models(list_models(provider), search)
        except (CatalogError, ProviderError, KeyError) as e:
            show(f"Can't list models: {e}")
            return True

        lines = [f"{name}: {len(models)} models" + (f" matching '{search}'" if search else "")]
        for m in models[:30]:
            tools = {True: "tools", False: "no tools", None: ""}[m.tools]
            free = "free" if m.free else ""
            details = ", ".join(x for x in (tools, free) if x)
            lines.append(f"  {m.id}" + (f"  ({details})" if details else ""))
        if len(models) > 30:
            lines.append(f"  ... {len(models) - 30} more; narrow with /models <search>")
        show("\n".join(lines))
        return True
