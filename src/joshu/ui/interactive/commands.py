"""Command handlers for interactive mode slash commands."""

import json

from rich.console import Console
from rich.table import Table


class CommandHandler:
    """Handler for slash commands."""

    def __init__(self, interactive_mode):
        self.interactive_mode = interactive_mode
        self.context_provider = interactive_mode.context_provider
        self.config_manager = interactive_mode.config_manager

    def handle_session_command(self, command: str) -> bool:
        """Handle session management commands."""
        if not self.context_provider:
            self.interactive_mode._show_message("❌ Context provider not available.")
            return True

        parts = command.split()

        if len(parts) == 1:
            session_id = self.context_provider.session_id
            session_short = session_id[:8]
            self.interactive_mode._show_message(
                f"📋 Current session: {session_short}... (Full ID: {session_id})"
            )
            return True

        subcommand = parts[1].lower()

        if subcommand == "help":
            self.interactive_mode._show_message("📚 Session Management Commands:")
            self.interactive_mode._show_message("")
            self.interactive_mode._show_message("  /session           - Show current session ID")
            self.interactive_mode._show_message("  /session list      - List all sessions")
            self.interactive_mode._show_message("  /session new       - Start a new session")
            self.interactive_mode._show_message(
                "  /session end       - End current session and start a new one"
            )
            self.interactive_mode._show_message(
                "  /session switch <id> - Switch to a session by ID (full or short)"
            )
            self.interactive_mode._show_message(
                "  /session delete <id> - Delete a session by ID (full or short)"
            )
            self.interactive_mode._show_message("  /session help      - Show this help message")
            self.interactive_mode._show_message("")
            self.interactive_mode._show_message(
                "💡 Tip: Use short IDs (first 8 characters) or full IDs"
            )
            return True

        if subcommand == "list":
            sessions = self.context_provider.list_sessions()
            if not sessions:
                self.interactive_mode._show_message("📭 No sessions found.")
                return True

            console = Console()
            table = Table(title="Available Sessions", show_header=True, header_style="bold magenta")
            table.add_column("Short ID", style="cyan", width=12)
            table.add_column("Full ID", style="dim", width=40)
            table.add_column("Start Time", style="green", width=20)
            table.add_column("Status", style="yellow", width=10)

            current_session_id = self.context_provider.session_id
            for session in sessions:
                short_id = session["short_id"]
                full_id = session["id"]
                start_time = session["start_time"]
                is_active = session.get("active", False)
                is_current = full_id == current_session_id

                status = "🟢 Active"
                if is_current:
                    status = "⭐ Current"
                    short_id = f"→ {short_id}"
                elif not is_active:
                    status = "⚫ Inactive"

                table.add_row(short_id, full_id, start_time, status)

            console.print(table)
            return True

        elif subcommand == "new":
            new_session_id = self.context_provider.new_session()
            self.interactive_mode._show_message(f"🆕 New session started: {new_session_id[:8]}...")
            return True

        elif subcommand == "switch":
            if len(parts) < 3:
                self.interactive_mode._show_message("❌ Usage: /session switch <session_id>")
                self.interactive_mode._show_message(
                    "💡 Tip: Use /session list to see available sessions"
                )
                return True

            session_id = parts[2]
            if self.context_provider.switch_session(session_id):
                self.interactive_mode._show_message(f"✅ Switched to session: {session_id[:8]}...")
            else:
                self.interactive_mode._show_message(f"❌ Session not found: {session_id}")
                self.interactive_mode._show_message(
                    "💡 Use /session list to see available sessions"
                )
            return True

        elif subcommand == "delete":
            if len(parts) < 3:
                self.interactive_mode._show_message("❌ Usage: /session delete <session_id>")
                self.interactive_mode._show_message(
                    "💡 Tip: Use /session list to see available sessions"
                )
                return True

            session_id = parts[2]
            current_session_id = self.context_provider.session_id

            if session_id == current_session_id or current_session_id.startswith(session_id):
                self.interactive_mode._show_message(
                    "❌ Cannot delete current session. Switch to another session first."
                )
                return True

            if self.context_provider.delete_session(session_id):
                self.interactive_mode._show_message(f"✅ Deleted session: {session_id[:8]}...")
            else:
                self.interactive_mode._show_message(f"❌ Session not found: {session_id}")
                self.interactive_mode._show_message(
                    "💡 Use /session list to see available sessions"
                )
            return True

        elif subcommand == "end":
            current_session_id = self.context_provider.session_id
            if self.context_provider.end_session():
                self.interactive_mode._show_message(
                    f"✅ Ended and deleted session: {current_session_id[:8]}..."
                )
                new_session_id = self.context_provider.new_session()
                self.interactive_mode._show_message(
                    f"🆕 Started new session: {new_session_id[:8]}..."
                )
            else:
                self.interactive_mode._show_message("❌ Failed to end current session")
            return True

        else:
            self.interactive_mode._show_message(f"❌ Unknown session command: {subcommand}")
            self.interactive_mode._show_message(
                "💡 Available commands: list, new, switch, delete, end, help"
            )
            self.interactive_mode._show_message("💡 Type '/session help' for detailed information")
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
            from joshu.core.storage import EntryType, QueryFilter

            filter = QueryFilter(entry_type=EntryType.PROMPT_HISTORY)
            self.interactive_mode.context_provider.storage.delete_entries(filter)
            self.interactive_mode.prompt_history._load_history()
            self.interactive_mode.command_history = []
            self.interactive_mode._show_message("✅ Command history cleared.")
            return True

        if command == "/new-session":
            return self.handle_session_command("/session new")

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
                "Switched to agent mode. I can now execute tasks from A to Z."
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
                "Switched to plan mode. I will break down tasks into actionable steps without executing them."
            )
            return True

        else:
            self.interactive_mode._show_message(f"Unknown command: {command}")
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
  /clear       - Clear command history
  /search \u003cquery\u003e - Search the web for information
  /session     - Show current session
  /session help - Show session management help
  /session list - List all sessions
  /session new - Start a new session
  /session end - End current session and start a new one
  /session switch <id> - Switch to a session
  /session delete <id> - Delete a session
  /memory      - Show memory commands help
  /memory status - Show semantic memory statistics
  /memory search <query> - Search for similar conversations
  /memory clear - Clear all semantic memories
  /history     - Show command history
  /help        - Show this help
  /config   - Show/set configuration
  /model    - Switch AI model
"""

        mode_help = {
            "agent": """
Current Mode: AGENT
  Description: Autonomous task execution mode. I can understand high-level goals and execute them from start to finish.

  Usage:
    - Simply describe your goal (e.g., "set up a Flask project")
    - I will automatically:
      1. Generate a step-by-step plan
      2. Execute each command safely
      3. Handle errors and ask for confirmation when needed
      4. Provide a final execution summary

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
  Description: Task planning mode. I break down tasks into actionable steps without executing them.

  Usage:
    - Describe a task or goal
    - I generate a numbered list of steps
    - You can review and execute the steps manually

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
                self.interactive_mode._show_message(f"Invalid configuration key: {key}")

    def handle_model_command(self, command: str):
        """Handle model switching commands."""
        parts = command.split()
        if len(parts) == 1:
            current_model = self.config_manager.get("model", "llama-3-8b")
            self.interactive_mode._show_message(f"Current model: {current_model}")
        elif len(parts) == 2:
            model = parts[1]
            if self.config_manager.set("model", model):
                self.config_manager.save_config()
                self.interactive_mode.model = model
                self.interactive_mode._show_message(f"Switched to model: {model}")
            else:
                self.interactive_mode._show_message(f"Failed to switch to model: {model}")
