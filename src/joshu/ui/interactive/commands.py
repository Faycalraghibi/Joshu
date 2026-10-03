"""Command handlers for interactive mode slash commands."""

import json


class CommandHandler:
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

    def handle_memory_command(self, command: str) -> bool:
        """Handle semantic memory commands."""
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
        """Handle slash commands."""
        if command.startswith("/session"):
            return self.handle_session_command(command)

        if command.startswith("/memory"):
            return self.handle_memory_command(command)

        if command == "/clear":
            self.interactive_mode.prompt_history.clear()
            self.interactive_mode.command_history = []
            self.interactive_mode._show_message("Input history cleared.")
            return True

        if command == "/new-session":
            return self.handle_session_command("/session new")

        if command == "/reset":
            return self.handle_session_command("/session new")

        if command == "/resume" or command.startswith("/resume "):
            return self.handle_resume_command(command)

        if command == "/cost":
            return self.handle_cost_command()

        if command == "/undo":
            return self.handle_undo_command()

        if command.startswith("/permissions"):
            return self.handle_permissions_command(command)

        elif command == "/history":
            self.display_history()
            return True

        elif command.startswith("/help"):
            self.show_help()
            return True

        elif command.startswith("/config"):
            self.handle_config_command(command)
            return True

        elif command.startswith("/search"):
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                self.interactive_mode._show_message("❌ Usage: /search <query>")
                self.interactive_mode._show_message(
                    "💡 Example: /search Python best practices 2024"
                )
                return True

            query = parts[1]

            from joshu.ui.cli_handlers.search_handler import handle_search_command

            handle_search_command(query, max_results=None)
            return True

        elif command.startswith("/model"):
            self.handle_model_command(command)
            return True

        elif command == "/agent":
            self.interactive_mode.interaction_mode = "agent"
            self.interactive_mode._show_message(
                "Switched to agent mode. I read, edit and run commands to finish tasks, "
                "asking before edits and shell commands."
            )
            return True

        elif command == "/ask":
            self.interactive_mode.interaction_mode = "ask"
            self.interactive_mode._show_message(
                "Switched to ask mode. I will answer questions directly without executing commands."
            )
            return True

        elif command == "/plan":
            self.interactive_mode.interaction_mode = "plan"
            self.interactive_mode._show_message(
                "Switched to plan mode. I investigate with read-only tools and propose a plan "
                "without changing anything."
            )
            return True

        elif command == "/commands":
            return self.handle_commands_list()

        elif command == "/agents":
            return self.handle_agents_list()

        else:
            return self.handle_custom_command(command)

    def handle_custom_command(self, command: str) -> bool:
        """Run a custom command from .joshu/commands or ~/.joshu/commands."""
        from joshu.core.custom_commands import discover_commands, split_command

        parsed = split_command(command)
        if parsed is None or parsed[0] not in discover_commands():
            self.interactive_mode._show_message(
                f"Unknown command: {command.split()[0]} (see /help and /commands)"
            )
            return True
        return self.interactive_mode.run_custom_command(command)

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
            f"  input tokens:  {usage['prompt_tokens']:,}\n"
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

    def handle_permissions_command(self, command: str) -> bool:
        """Show or set the agent permission mode: /permissions [default|accept_edits|bypass]."""
        from joshu.core.permissions import PermissionMode

        parts = command.split()
        if len(parts) == 1:
            current = self.config_manager.get("permission_mode", "default")
            self.interactive_mode._show_message(
                f"Permission mode: {current}\n"
                "  default      - ask before edits, shell commands and other risky tools\n"
                "  accept_edits - file edits run without asking; shell still asks\n"
                "  bypass       - everything runs; commands flagged unsafe still ask\n"
                "Use /plan for read-only mode."
            )
            return True

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

    def display_history(self):
        """Display command history."""
        history_strings = self.interactive_mode.prompt_history.load_history_strings()

        if not history_strings:
            self.interactive_mode._show_message("No command history")
            return

        self.interactive_mode._show_message("Command History:")
        for i, cmd in enumerate(history_strings[-20:], 1):
            self.interactive_mode._show_message(f"{i}: {cmd}")

    def show_help(self):
        """Display help information."""
        base_help = """
interactive Mode Help:

Keyboard Shortcuts:
  Ctrl+R    - Reverse search
  Ctrl+J    - Line navigation down
  Ctrl+K    - Line navigation up
  Ctrl+B    - Send command to background bash
  Ctrl+C    - Interrupt current operation
  Ctrl+D    - Exit
  Ctrl+L    - Clear screen
  Ctrl+T    - Toggle command suggestions

Vim Mode:
  ESC       - Switch to NORMAL mode
  i         - Switch to INSERT mode
  h/j/k/l   - Left/Down/Up/Right
  w/b       - Word forward/backward
  :         - Command mode

Special Commands:
  !command  - Execute bash command
  !!        - Repeat last bash command
  !n        - Execute nth bash command from history
  @file     - Inject file content
  @@file    - Inject and execute file content
  @file:n-m - Inject lines n to m from file
  /clear       - Clear input history (up-arrow recall)
  /search \u003cquery\u003e - Search the web for information
  /session     - Show the current agent session (/session help for more)
  /session list - Saved sessions in this directory
  /session new - Start a new conversation
  /session switch <id> - Continue a saved session
  /session delete <id> - Delete a saved session
  /memory      - Show memory commands help
  /memory status - Show semantic memory statistics
  /memory search <query> - Search for similar conversations
  /memory clear - Clear all semantic memories
  /history     - Show your recent input
  /help        - Show this help
  /reset       - Start a new conversation (same as /session new)
  /undo        - Revert the agent's file edits from its last request
  /cost        - Tokens and cost of this conversation
  /resume [id] - List saved sessions, or continue one
  /commands    - List custom commands (.joshu/commands/*.md|toml)
  /agents      - List sub-agents (.joshu/agents/*.md)
  /permissions - Show or set the agent permission mode
  /config   - Show/set configuration
  /model    - Switch AI model
"""

        mode_help = {
            "agent": """
Current Mode: AGENT
  Description: I work on your task with tools - reading and searching files, editing them,
  and running commands - and see each result before deciding the next step.

  Usage:
    - Describe your goal (e.g., "add a --verbose flag to the CLI and test it")
    - Edits and shell commands show a preview and ask first
      ([y]es / [a]lways this session / [n]o); change this with /permissions
    - Ctrl+C interrupts the current task; /reset starts a new conversation

  Example: "create a Python virtual environment and install requests"

  Mode Switching:
    /ask   - Switch to ask mode (information & explanations)
    /plan  - Switch to plan mode (planning without execution)
""",
            "ask": """
Current Mode: ASK
  Description: Information & explanation mode. I answer questions directly without executing commands.

  Usage:
    - Ask any question (e.g., "what is Python?", "how does Git work?")
    - I provide clear, informative answers
    - No commands are generated or executed

  Example: "explain how virtual environments work in Python"

  Mode Switching:
    /agent - Switch to agent mode (autonomous task execution)
    /plan  - Switch to plan mode (task planning)
""",
            "plan": """
Current Mode: PLAN
  Description: Read-only planning mode. I investigate the codebase with read-only tools
  and propose a plan; edits and commands are not allowed.

  Usage:
    - Describe a task or goal
    - I explore the relevant files and return a numbered plan
    - Switch to /agent to carry it out

  Example: "plan how to set up a Flask project"

  Mode Switching:
    /agent - Switch to agent mode (autonomous task execution)
    /ask   - Switch to ask mode (information & explanations)
""",
        }

        help_text = base_help + "\n" + mode_help.get(self.interactive_mode.interaction_mode, "")
        self.interactive_mode._show_message(help_text)

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
        """Handle model switching commands."""
        parts = command.split()
        if len(parts) == 1:
            current_model = self.config_manager.get("model")
            self.interactive_mode._show_message(f"Current model: {current_model}")
        elif len(parts) == 2:
            model = parts[1]
            if self.config_manager.set("model", model):
                self.config_manager.save_config()
                self.interactive_mode.model = model
                self.interactive_mode._show_message(f"Switched to model: {model}")
            else:
                self.interactive_mode._show_message(f"Failed to switch to model: {model}")
