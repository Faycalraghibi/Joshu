"""
Hook Events.

Defines the lifecycle events that hooks can intercept.
"""

from enum import Enum


class HookEvent(str, Enum):
    """
    Agent lifecycle events that can be intercepted by hooks.

    Hooks are executed at specific points in the agent workflow:
    - SESSION_START: Beginning of a new session
    - BEFORE_AGENT: Before agent processes a prompt
    - BEFORE_TOOL_SELECTION: Before selecting tools for a request
    - BEFORE_TOOL: Before executing a specific tool
    - AFTER_TOOL: After a tool has been executed
    - AFTER_AGENT: After agent generates a response
    - SESSION_END: End of a session
    """

    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Agent processing
    BEFORE_AGENT = "before_agent"
    AFTER_AGENT = "after_agent"

    # Tool execution
    BEFORE_TOOL_SELECTION = "before_tool_selection"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"

    @classmethod
    def from_string(cls, value: str) -> "HookEvent":
        """Create HookEvent from string value."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid hook event: {value}")


# Exit codes for hook scripts
class HookExitCode:
    """
    Exit codes for hook scripts.

    0 = Allow (continue execution)
    2 = Block (abort execution)
    other = Warn (log warning and continue)
    """

    ALLOW = 0
    BLOCK = 2
