from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from joshu.core.context_provider import ContextProvider
from joshu.core.translation_cache import TranslationCache
from joshu.models.inference import get_model
from joshu.tools.parsing_utils import (
    extract_command_and_explanation,
    parse_json_response,
)
from joshu.tools.system_info import get_system_info

logger = logging.getLogger(__name__)
# Reduce logging verbosity - only show warnings and errors
logger.setLevel(logging.WARNING)

# Global variable to store the connection status
_connection_established = False
_connection_error = None

# Global cache instance (initialized lazily)
_translation_cache: Optional[TranslationCache] = None


def establish_connection(model_name: str = "default") -> bool:
    """Establish connection to the model service when assistant is launched."""
    global _connection_established, _connection_error

    if _connection_established:
        return True

    try:
        # Try to establish connection to OpenRouter if API key is available
        import os

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            from joshu.models.openrouter import get_openrouter_client

            client = get_openrouter_client(model_name)
            if client:
                _connection_established = True
                _connection_error = None
                logger.info("Connection to OpenRouter established successfully")
                return True

        # For local models, try to get model from pool
        from joshu.models.pool import get_model_pool

        pool = get_model_pool()
        available_providers = pool.get_available_providers()
        if available_providers:
            _connection_established = True
            _connection_error = None
            logger.info("Local model connection established successfully")
            return True

    except Exception as e:
        _connection_error = str(e)
        logger.warning(f"Failed to establish connection: {e}")
        return False

    return False


@dataclass
class Translation:
    """Translation result with optional execution flag."""

    command: str
    explanation: str
    needs_execution: bool = True  # If False, just display the response without asking for execution


COMMON_PATTERNS: List[Tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"list\s+all\s+python\s+files\s+modified\s+(today|in\s+the\s+last\s+day)\b", re.I
        ),
        'find . -name "*.py" -mtime -1',
        "List Python files modified in the last 24 hours using find and mtime.",
    ),
    (
        re.compile(r"show\s+disk\s+usage(\s+of\s+current\s+directory)?\b", re.I),
        "du -sh .",
        "Summarize disk usage of the current directory in human-readable form.",
    ),
    (
        re.compile(r"find\s+large\s+files\s+over\s+(\d+)\s*mb\b", re.I),
        "find . -type f -size +{size}M -exec ls -lh {} \\;",
        "Find files larger than the given size and list details.",
    ),
    (
        re.compile(r"find\s+all\s+python\s+files\b", re.I),
        'find . -name "*.py"',
        "Find all Python files recursively from the current directory.",
    ),
    (
        re.compile(
            r"(show|tell|what|give|provide)(\s+is)?\s+(me\s+)?(the\s+)?(conversation\s+)?(history|memory|context)\b",
            re.I,
        ),
        'echo "Use the memory summary feature"',
        "Provide a summary of the conversation history and memory.",
    ),
    # File operations patterns
    (
        re.compile(
            r"(show\s+me\s+|display\s+|list\s+)?(the\s+)?(structure|tree)\s+of\s+(this\s+)?(project|directory)\b",
            re.I,
        ),
        'echo "Use the directory structure feature"',
        "Show the directory structure of the current project.",
    ),
    (
        re.compile(r"find\s+(configuration|config)\s+files\b", re.I),
        'echo "Use the configuration file finder feature"',
        "Find configuration files in the current directory.",
    ),
    (
        re.compile(
            r"(what\'?s\s+in\s+|show\s+me\s+|list\s+)(the\s+)?(log|logs)\s+(directory|folder)\b",
            re.I,
        ),
        'echo "Use the log directory listing feature"',
        "Show contents of the log directory.",
    ),
    (
        re.compile(r"(backup|copy)\s+(my\s+)?(source\s+)?code\b", re.I),
        'echo "Use the backup feature"',
        "Create a backup of your source code.",
    ),
    # Note: Code generation requests are not pattern-matched here. They are handled by the dedicated `joshu code` command.
]


def _handle_conversational_query(
    text: str, context_provider: Optional[ContextProvider] = None, model_name: str = "default"
) -> Optional[Translation]:
    """
    Handle conversational queries with direct responses instead of command translation.

    Returns a Translation with an echo command that shows a conversational response.
    """
    text_lower = text.lower().strip()

    # Handle simple greetings with friendly responses
    if text_lower in ["hi", "hello", "hey", "greetings"]:
        return Translation(
            command='echo "Hello! I\'m Joshu, your AI assistant. I can help you with:\n- Running commands: "list all files" or "show disk usage"\n- Code generation: use \'joshu code "your request"\'\n- General questions and conversations\n\nWhat would you like to do?"',
            explanation="Greeting response - providing an introduction and helpful information",
            needs_execution=False,  # Conversational response, no execution needed
        )

    # For other conversational queries, use LLM to generate a direct response
    try:
        import os

        from joshu.models.openrouter import chat_completion

        # Try OpenRouter first for conversational responses
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

        # Auto-enable cloud if API key is present (unless explicitly disabled)
        use_cloud_env = os.getenv("JOSHU_USE_CLOUD", "").lower()
        if use_cloud_env == "false":
            use_cloud = False
        elif use_cloud_env == "true":
            use_cloud = True
        elif openrouter_key or has_model_key:
            use_cloud = True  # Auto-enable if API key found
        else:
            use_cloud = False

        if (openrouter_key or has_model_key) and use_cloud:
            system_message = """You are Joshu, a friendly AI assistant. The user is asking a conversational question or making a comment.
Provide a helpful, direct response. You don't need to generate commands for this - just answer their question naturally.
Keep responses concise and friendly."""

            model_name_env = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": text},
            ]

            response = chat_completion(
                messages, model=model_name_env, temperature=0.7, max_tokens=512
            )
            if response:
                # Return response as an echo command so it displays to the user
                return Translation(
                    command=f'echo """{response}"""',
                    explanation="Conversational response - providing direct answer to user's question",
                    needs_execution=False,  # Conversational response, no execution needed
                )

        # Fallback to local model for conversational responses
        from joshu.models.pool import get_model_pool

        pool = get_model_pool()
        available_providers = pool.get_available_providers()
        if available_providers:
            # Use first available provider (prioritized by pool: OpenRouter > local model > llama.cpp > Echo)
            model_provider = available_providers[0]
            conversational_prompt = f"""You are Joshu, a friendly AI assistant. The user said: "{text}"
Provide a helpful, direct response. Keep it concise and friendly. Do not generate commands."""

            response = model_provider.generate(
                conversational_prompt, temperature=0.7, max_tokens=256
            )
            if response:
                # Clean any JSON or command formatting from response
                cleaned_response = response.strip()
                if cleaned_response.startswith("{") and '"command"' in cleaned_response:
                    # If model returned JSON, extract explanation or provide default
                    cleaned_response = "I understand your question. I'm here to help with both conversations and command execution. Feel free to ask me anything!"

                return Translation(
                    command=f'echo """{cleaned_response}"""',
                    explanation="Conversational response - providing direct answer",
                    needs_execution=False,  # Conversational response, no execution needed
                )

    except Exception as e:
        logger.debug(f"Conversational response generation failed: {e}")

    # Fallback for simple queries
    return Translation(
        command="echo \"I understand. How can I help you? You can ask me questions, request commands, or use 'joshu code' for code generation.\"",
        explanation="Default conversational response",
        needs_execution=False,  # Conversational response, no execution needed
    )


def generate_memory_summary_with_llm(
    context_provider: ContextProvider, prompt: str
) -> Optional[Translation]:
    """Generate a memory summary using the LLM."""
    try:
        # Get context summary from the context provider
        context_summary = context_provider.generate_memory_summary()

        # Create a prompt for the LLM to summarize the context
        summary_prompt = f"""You are a helpful assistant that summarizes conversation history and memory.

The user is asking for a summary of the conversation history and memory. Here's what we have:

{context_summary}

Please provide a natural, conversational summary of what we've discussed and what we know. Be concise but informative."""

        # Try to use OpenRouter first
        from joshu.models.openrouter import chat_completion

        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes conversation history and memory.",
            },
            {"role": "user", "content": summary_prompt},
        ]

        response = chat_completion(messages, temperature=0.3, max_tokens=500)
        if response:
            # Handle echo model response
            if response.startswith("Echo:"):
                # Use the context summary directly
                return Translation(
                    command=f'echo """{context_summary}"""',
                    explanation="Displaying conversation history and memory summary",
                )
            # Return a command that will display the summary
            return Translation(
                command=f'echo """{response}"""',
                explanation="Displaying conversation history and memory summary",
            )

        # Fallback to local model
        from joshu.models.pool import get_model_pool

        pool = get_model_pool()
        available_providers = pool.get_available_providers()
        if available_providers:
            model_provider = available_providers[0]
            response = model_provider.generate(summary_prompt, temperature=0.3, max_tokens=500)
            if response:
                # Handle echo model response
                if response.startswith("Echo:"):
                    # Use the context summary directly
                    return Translation(
                        command=f'echo """{context_summary}"""',
                        explanation="Displaying conversation history and memory summary",
                    )
                return Translation(
                    command=f'echo """{response}"""',
                    explanation="Displaying conversation history and memory summary",
                )
    except Exception as e:
        logger.warning(f"Failed to generate memory summary with LLM: {e}")

    # Fallback to simple context summary
    context_summary = context_provider.generate_memory_summary()
    return Translation(
        command=f'echo """{context_summary}"""',
        explanation="Displaying conversation history and memory summary",
    )


def _is_conversational_query(text: str) -> bool:
    """
    Detect if a query is conversational (should get a direct response) vs a command request.

    Returns True if the query appears to be conversational/chat rather than a command request.
    """
    text_lower = text.lower().strip()

    # Simple greetings - definitely conversational
    if text_lower in [
        "hi",
        "hello",
        "hey",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
    ]:
        return True

    # Questions that don't request actions - conversational
    question_patterns = [
        r"^(what|how|why|when|where|who|is|are|can|do|does|did|will|would)\s+.*\?",
        r".*\?$",  # Ends with question mark
    ]
    for pattern in question_patterns:
        if re.match(pattern, text_lower):
            # But exclude questions that clearly request commands
            command_indicators = [
                "how to",
                "how do i",
                "how can i",
                "show me",
                "list",
                "find",
                "display",
                "create",
                "delete",
                "run",
                "execute",
                "get",
            ]
            if not any(indicator in text_lower for indicator in command_indicators):
                return True

    # General chat/phrases without action verbs
    if len(text_lower.split()) <= 3 and not any(
        word in text_lower for word in ["list", "show", "find", "get", "create", "delete", "run"]
    ):
        return True

    return False


def _cache_key(text: str) -> str:
    """Cache key: the same request means a different command on another OS or directory."""
    import platform

    return f"{platform.system()}|{os.getcwd()}|{text}"


def translate_to_command(
    prompt: str,
    context_provider: Optional[ContextProvider] = None,
    model_name: str = "default",
    use_cache: bool = True,
) -> Optional[Translation]:
    text = prompt.strip()

    # Only log the prompt for debugging if needed
    logger.debug(f"Translating prompt: {text}")

    # Initialize cache if needed and cache is enabled
    global _translation_cache
    if use_cache and _translation_cache is None:
        try:
            from joshu.core.config import get_config_manager

            config_manager = get_config_manager()

            # Only initialize if cache is enabled in config
            if config_manager.get("cache_enabled", True):
                cache_dir = config_manager.get("cache_dir", "./cache")
                similarity_threshold = config_manager.get("cache_similarity_threshold", 0.85)
                max_entries = config_manager.get("cache_max_entries", 1000)

                _translation_cache = TranslationCache(
                    cache_dir=cache_dir,
                    similarity_threshold=similarity_threshold,
                    max_entries=max_entries,
                    semantic_matching=False,
                )
                logger.debug("Translation cache initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize translation cache: {e}")
            _translation_cache = None

    # Check cache first if enabled
    if use_cache and _translation_cache is not None:
        try:
            cached_result = _translation_cache.get(_cache_key(text))
            if cached_result:
                command, explanation = cached_result
                logger.debug(f"Using cached translation for: {text}")
                return Translation(command=command, explanation=explanation)
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")

    # Check if this is a conversational query first
    if _is_conversational_query(text):
        # Return a conversational response instead of a command
        return _handle_conversational_query(text, context_provider, model_name)

    # Check connection status
    global _connection_established, _connection_error
    if not _connection_established:
        logger.debug("Attempting to establish connection...")
        establish_connection(model_name)

    # First try pattern matching
    for pattern, template, explanation in COMMON_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        logger.debug(f"Pattern matched: {pattern.pattern}")

        # Code generation requests are intentionally not handled here; the `joshu code` command covers them.

        # Special handling for memory/history requests
        if re.search(
            r"(show|tell|what|give|provide)(\s+is)?\s+(me\s+)?(the\s+)?(conversation\s+)?(history|memory|context)\b",
            text,
            re.I,
        ):
            if context_provider:
                # Generate memory summary using LLM
                return generate_memory_summary_with_llm(context_provider, prompt)
            else:
                command = template
                if "{size}" in template and m.groups():
                    size = m.group(1)
                    command = template.format(size=size)

                # Adapt command for Windows if needed
                command = adapt_command_for_windows(command)

                return Translation(command=command, explanation=explanation)

        # Special handling for file operations
        if re.search(
            r"(show\s+me\s+|display\s+|list\s+)?(the\s+)?(structure|tree)\s+of\s+(this\s+)?(project|directory)\b",
            text,
            re.I,
        ):
            # Handle directory structure requests
            import json
            import os

            from joshu.tools.filesystem import get_directory_structure

            structure = get_directory_structure(os.getcwd())
            formatted_structure = json.dumps(structure, indent=2)
            return Translation(
                command=f'echo """{formatted_structure}"""',
                explanation="Displaying the directory structure of the current project.",
            )

        if re.search(r"find\s+(configuration|config)\s+files\b", text, re.I):
            # Handle configuration file requests
            import os

            from joshu.tools.filesystem import find_files_by_extension

            config_files = []
            config_extensions = [
                ".conf",
                ".cfg",
                ".config",
                ".ini",
                ".yaml",
                ".yml",
                ".json",
                ".toml",
                ".xml",
            ]
            for ext in config_extensions:
                config_files.extend(find_files_by_extension(os.getcwd(), ext))

            if config_files:
                files_list = "\n".join(config_files)
                return Translation(
                    command=f'echo """{files_list}"""',
                    explanation="Found configuration files in the current directory.",
                )
            else:
                return Translation(
                    command='echo "No configuration files found in the current directory."',
                    explanation="No configuration files were found.",
                )

        if re.search(
            r"(what\'?s\s+in\s+|show\s+me\s+|list\s+)(the\s+)?(log|logs)\s+(directory|folder)\b",
            text,
            re.I,
        ):
            # Handle log directory requests
            import os

            from joshu.tools.filesystem import (
                format_directory_listing,
                list_directory_contents,
            )

            log_dirs = ["log", "logs", "Log", "Logs"]
            for log_dir in log_dirs:
                log_path = os.path.join(os.getcwd(), log_dir)
                if os.path.exists(log_path) and os.path.isdir(log_path):
                    files = list_directory_contents(log_path)
                    formatted_listing = format_directory_listing(files)
                    return Translation(
                        command=f'echo """Contents of {log_dir}/:\n{formatted_listing}"""',
                        explanation=f"Displaying contents of the {log_dir} directory.",
                    )

            # If no log directory found, list files that look like log files
            from joshu.tools.filesystem import find_files_by_extension

            log_files = []
            log_extensions = [".log", ".out", ".err"]
            for ext in log_extensions:
                log_files.extend(find_files_by_extension(os.getcwd(), ext))

            if log_files:
                files_list = "\n".join(log_files)
                return Translation(
                    command=f'echo """Log files found:\n{files_list}"""',
                    explanation="Found log files in the current directory.",
                )
            else:
                return Translation(
                    command='echo "No log directory or log files found in the current directory."',
                    explanation="No log directory or log files were found.",
                )

        if re.search(r"(backup|copy)\s+(my\s+)?(source\s+)?code\b", text, re.I):
            # Handle backup requests
            import os
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"backup_{timestamp}"
            return Translation(
                command=f'echo "To backup your source code, create a copy of your project directory to {backup_dir}"',
                explanation=f"Suggest creating a backup of your source code in a {backup_dir} directory.",
            )

        command = template
        if "{size}" in template and m.groups():
            size = m.group(1)
            command = template.format(size=size)

        # Adapt command for Windows if needed
        command = adapt_command_for_windows(command)

        # Store in cache if enabled
        if use_cache and _translation_cache is not None:
            try:
                _translation_cache.put(_cache_key(text), command, explanation)
            except Exception as e:
                logger.warning(f"Failed to cache translation: {e}")

        return Translation(command=command, explanation=explanation)

    # If pattern matching fails, try LLM-based translation
    return translate_with_llm(prompt, context_provider, model_name, use_cache)


def adapt_command_for_windows(command: str, system_info: Optional[str] = None) -> str:
    """Adapt Unix commands for Windows."""
    # If system_info is not provided, detect it
    if system_info is None:
        from joshu.tools.system_info import get_system_info

        system_info = get_system_info()

    # If we're not on Windows, no adaptation is needed
    if "Windows" not in system_info:
        return command

    # Common Unix to Windows command mappings
    if command.startswith("ls"):
        return command.replace("ls", "dir")
    elif command.startswith("du -sh"):
        return "dir"  # Simple replacement for disk usage
    elif command.startswith("find . -name"):
        # Convert find command to Windows equivalent
        if "*.py" in command:
            return "dir /s *.py"
    elif command.startswith("pwd"):
        return "cd"
    elif command.startswith("cat"):
        return command.replace("cat", "type")
    elif command.startswith("type "):
        # Already a Windows command
        return command

    # Return original command if no adaptation is needed
    return command


def translate_with_llm(
    prompt: str,
    context_provider: Optional[ContextProvider] = None,
    model_name: str = "default",
    use_cache: bool = True,
) -> Optional[Translation]:
    """Translate natural language to command using LLM."""
    try:
        # Try OpenRouter first
        translation = translate_with_openrouter(prompt, context_provider, model_name)
        if translation:
            command = translation["command"]
            explanation = translation.get("explanation", "")
            # Adapt command for Windows if needed
            command = adapt_command_for_windows(command)
            # Check if this is a conversational response (needs_execution=False)
            # PRIORITY: Check explanation first - it's the most reliable indicator
            explanation_lower = explanation.lower()

            # Check explanation for conversational indicators
            conversational_explanation_keywords = [
                "conversational response",
                "direct response",
                "direct answer",
                "to user's query",
                "to user's question",
                "user's query",
                "user's question",
                "answering",
                "providing answer",
                "providing response",
            ]

            is_explanation_conversational = any(
                keyword in explanation_lower for keyword in conversational_explanation_keywords
            )

            # Also check command format - long echo commands with triple quotes are conversational
            command_normalized = command.replace('\\"', '"').replace("\\'", "'")
            is_command_conversational = (
                '"""' in command_normalized  # Has triple quotes
                or command_normalized.startswith('echo "')
                and len(command) > 100  # Long echo command
            )

            # If either the explanation OR command suggests conversational, it's conversational
            is_conversational = is_explanation_conversational or is_command_conversational

            # Force needs_execution to False if conversational
            needs_execution = not is_conversational

            # Store in cache if it's an actual command (not conversational)
            if use_cache and not is_conversational and _translation_cache is not None:
                try:
                    _translation_cache.put(_cache_key(prompt.strip()), command, explanation)
                except Exception as e:
                    logger.warning(f"Failed to cache translation: {e}")

            return Translation(
                command=command, explanation=explanation, needs_execution=needs_execution
            )

        # If OpenRouter returned None, it might be a conversational response
        # Try to generate a conversational response using OpenRouter
        if not translation:
            try:
                import os

                from joshu.models.openrouter import chat_completion

                openrouter_key = os.getenv("OPENROUTER_API_KEY")
                if openrouter_key:
                    system_message = """You are Joshu, a friendly AI assistant. The user's request wasn't a command request.
Provide a helpful, direct conversational response. Keep it concise and friendly."""
                    model_name_env = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
                    messages = [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt},
                    ]
                    response = chat_completion(
                        messages, model=model_name_env, temperature=0.7, max_tokens=512
                    )
                    if response:
                        return Translation(
                            command=f'echo """{response}"""',
                            explanation="Conversational response",
                            needs_execution=False,  # Conversational response, no execution needed
                        )
            except Exception:
                pass  # Fall through to local model

        # Fallback to local model API (which falls back to deprecated direct llama.cpp loading)
        translation = translate_with_local_model_api(prompt, context_provider, model_name)
        if translation:
            command = translation.command
            # Adapt command for Windows if needed
            command = adapt_command_for_windows(command)
            # Preserve the needs_execution flag from the translation
            needs_execution = getattr(translation, "needs_execution", True)
            return Translation(
                command=command,
                explanation=translation.explanation,
                needs_execution=needs_execution,
            )

        # Final fallback to deprecated local model (for backward compatibility)
        translation = translate_with_local_model(prompt, context_provider, model_name)
        if translation:
            command = translation.command
            # Adapt command for Windows if needed
            command = adapt_command_for_windows(command)
            # Preserve the needs_execution flag from the translation
            needs_execution = getattr(translation, "needs_execution", True)
            return Translation(
                command=command,
                explanation=translation.explanation,
                needs_execution=needs_execution,
            )

    except Exception as e:
        logger.warning(f"LLM translation failed: {e}")

    return None


def translate_with_openrouter(
    prompt: str, context_provider: Optional[ContextProvider] = None, model_name: str = "default"
) -> Optional[Dict[str, str]]:
    """Translate using OpenRouter API."""
    from joshu.models.openrouter import (
        translate_command_with_openrouter as openrouter_translate,
    )

    # If we have a context provider, use it to enhance the translation
    if context_provider:
        # Update context with the current request
        context_provider.add_to_history("user", prompt)

        # Get relevant context for the LLM
        context_messages = context_provider.get_relevant_context(prompt)

        # Add the current prompt as a user message
        context_messages.append({"role": "user", "content": prompt})

        # Use the enhanced context-aware translation with system info from context provider
        system_info = context_provider.system_info if context_provider.system_info else None
        return translate_command_with_openrouter_context_aware(
            context_messages, system_info, model_name
        )

    # Fallback to original implementation
    result = openrouter_translate(prompt)

    # If the result is not valid, try to extract command and explanation from the raw response
    if not result:
        # Try to get a raw response and parse it manually
        import os

        from joshu.models.openrouter import chat_completion

        system_info = get_system_info()
        system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.

IMPORTANT: Only generate commands when the user explicitly requests an action.
For conversational queries (greetings, questions, comments), provide a natural response instead of JSON.

When a command IS needed, respond with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

For conversational queries, provide a natural text response (not JSON).

User request:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Use the default model from environment
        model_name_env = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
        response = chat_completion(messages, model=model_name_env, temperature=0.1, max_tokens=256)
        if response:
            # Try to extract command and explanation from the response
            command, explanation = extract_command_and_explanation(response)
            if command and explanation:
                return {"command": command, "explanation": explanation}

    return result


def translate_command_with_openrouter_context_aware(
    messages: List[Dict[str, str]], system_info: Optional[str] = None, model_name: str = "default"
) -> Optional[Dict[str, str]]:
    """Translate using OpenRouter API with context awareness."""
    from joshu.models.openrouter import chat_completion

    # Use provided system_info or get it from the system
    if system_info is None:
        system_info = get_system_info()

    system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
You have access to conversation history and user preferences to provide better responses.

IMPORTANT: Only generate commands when the user explicitly requests an action (like "list files", "show disk usage", "find all python files").
For conversational queries (greetings, general questions, comments), return a helpful conversational response instead.

When a command is needed, respond with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

For conversational queries, you can provide direct helpful responses.

User request:"""

    # Prepend system prompt to messages
    full_messages = [{"role": "system", "content": system_prompt}]

    # Add context messages, but make sure we don't duplicate system messages
    for msg in messages:
        # Skip system messages that contain example responses to avoid duplication
        # But keep system information messages as they contain valuable context
        if msg["role"] != "system" or "Example response" not in msg["content"]:
            full_messages.append(msg)

    # Use the specified model
    response = chat_completion(full_messages, model=model_name, temperature=0.1, max_tokens=256)
    if not response:
        return None

    try:
        # Use utility function to parse JSON response
        data = parse_json_response(response)
        if data and isinstance(data, dict) and ("command" in data or "explanation" in data):
            command = data.get("command", "").strip()
            explanation = data.get("explanation", "").strip()

            if command and explanation:
                return {"command": command, "explanation": explanation}

            # If JSON but not command format, might be conversational
            logger.debug("Response is JSON but not command format - treating as conversational")
            # Return it as a conversational response dict
            return {
                "command": f'echo """{response}"""',
                "explanation": "Conversational response - direct answer to user's question",
            }

        # Not JSON - this is likely a conversational response
        # Return it as a conversational response dict
        logger.debug(f"OpenRouter returned conversational response (not JSON): {response[:100]}...")
        return {
            "command": f'echo """{response}"""',
            "explanation": "Conversational response - direct answer to user's question",
        }
    except Exception as e:
        logger.debug(f"Error processing OpenRouter response: {e}")
        return None

    return None


def translate_with_local_model_api(
    prompt: str,
    context_provider: Optional[ContextProvider] = None,
    model_name: Optional[str] = None,
) -> Optional[Translation]:
    """
    Translate using local model API provider.
    """
    from joshu.models.pool import get_model_pool

    system_info = get_system_info()

    # Build context-aware prompt
    if context_provider:
        context_messages = context_provider.get_relevant_context(prompt)
        context_str = "\nConversation History:\n"
        for msg in context_messages:
            # Skip system messages that contain system information to avoid duplication
            if msg["role"] != "system" or "System Information:" not in msg["content"]:
                context_str += f"{msg['role']}: {msg['content']}\n"

        memory_entries = context_provider.memory_store.kv
        if memory_entries:
            context_str += "\nUser Preferences:\n"
            for key, value in memory_entries.items():
                context_str += f"- {key}: {value}\n"

        system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
Use the following context to provide better responses:

{context_str}

IMPORTANT: Only generate commands when the user explicitly requests an action (like "list files", "show disk usage", "run a script").
For conversational queries (greetings, general questions, comments), provide a helpful conversational response instead of a command.

When a command IS needed, respond with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

For conversational queries, provide a natural response (not JSON).

User request:"""
    else:
        system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.

IMPORTANT: Only generate commands when the user explicitly requests an action (like "list files", "show disk usage", "run a script").
For conversational queries (greetings, general questions, comments), provide a helpful conversational response instead of a command.

When a command IS needed, respond with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

For conversational queries, provide a natural response (not JSON).

User request:"""

    try:
        pool = get_model_pool()
        # Try to get local model provider
        local_provider = pool.get_provider(name="local")
        if not local_provider or not local_provider.is_available():
            logger.debug("Local model provider not available")
            return None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = local_provider.chat_completion(messages, temperature=0.1, max_tokens=512)

        if not response:
            return None

        logger.debug(f"Local model API response: {response}")

        # Try to parse JSON response
        # Handle case where response might have extra text around JSON
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]  # Remove ```json
        if response.startswith("```"):
            response = response[3:]  # Remove ```
        if response.endswith("```"):
            response = response[:-3]  # Remove ```

        # Strip any leading/trailing whitespace that might remain
        response = response.strip()

        logger.debug(f"Cleaned response: {response}")

        # Check if response is JSON (command translation) or conversational text
        try:
            data = json.loads(response)
            # It's JSON - check if it has command/explanation structure
            if isinstance(data, dict) and ("command" in data or "explanation" in data):
                command = data.get("command", "").strip()
                explanation = data.get("explanation", "").strip()

                if command and explanation:
                    return Translation(command=command, explanation=explanation)
            # If JSON but not command format, might be conversational response
            # Fall through to handle as conversational
        except (json.JSONDecodeError, ValueError):
            # Not JSON - this is likely a conversational response
            # Check if it looks like a command request that should have been JSON
            if any(
                word in response.lower()
                for word in ["command", "run", "execute", "list", "show", "find"]
            ):
                # Might be a description of a command - try to extract
                logger.debug("Response appears to describe a command but isn't JSON format")
            else:
                # This is a conversational response - return it as an echo command
                logger.debug("Response appears to be conversational, returning as echo command")
                return Translation(
                    command=f'echo """{response}"""',
                    explanation="Conversational response - providing direct answer to user's question",
                    needs_execution=False,  # Conversational response, no execution needed
                )

        # If we got here, the response wasn't in expected format
        # For conversational responses that don't match patterns, return them as-is
        if not response.startswith("{") and '"command"' not in response:
            return Translation(
                command=f'echo """{response}"""',
                explanation="Direct response to user's query",
                needs_execution=False,  # Conversational response, no execution needed
            )

        # If we still have the response but it's not handled, return None
        return None
    except Exception as e:
        logger.warning(f"Local model translation failed: {e}")

    return None


def translate_with_local_model(
    prompt: str, context_provider: Optional[ContextProvider] = None, model_name: str = "default"
) -> Optional[Translation]:
    """
    Translate using local model (DEPRECATED: Use translate_with_local_model_api instead).

    This function is kept for backward compatibility but will be removed in a future version.
    Please migrate to local model API by setting LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER environment variables.
    """
    import warnings

    warnings.warn(
        "translate_with_local_model is deprecated. Use translate_with_local_model_api instead. "
        "Set LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER environment variables.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Try local model API first, then fall back to old direct llama.cpp loading logic
    local_result = translate_with_local_model_api(prompt, context_provider, model_name)
    if local_result:
        return local_result

    # Fallback to old local model implementation
    system_info = get_system_info()

    # Build context-aware prompt
    if context_provider:
        context_messages = context_provider.get_relevant_context(prompt)
        context_str = "\nConversation History:\n"
        for msg in context_messages:
            # Skip system messages that contain system information to avoid duplication
            if msg["role"] != "system" or "System Information:" not in msg["content"]:
                context_str += f"{msg['role']}: {msg['content']}\n"

        memory_entries = context_provider.memory_store.kv
        if memory_entries:
            context_str += "\nUser Preferences:\n"
            for key, value in memory_entries.items():
                context_str += f"- {key}: {value}\n"

        system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
Use the following context to provide better responses:

{context_str}

IMPORTANT: Only generate commands when the user explicitly requests an action (like "list files", "show disk usage", "run a script").
For conversational queries (greetings, general questions, comments), provide a helpful conversational response instead of a command.

When a command IS needed, respond with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

For conversational queries, provide a natural response (not JSON).

User request:"""
    else:
        system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.

IMPORTANT: Only generate commands when the user explicitly requests an action (like "list files", "show disk usage", "run a script").
For conversational queries (greetings, general questions, comments), provide a helpful conversational response instead of a command.

When a command IS needed, respond with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

For conversational queries, provide a natural response (not JSON).

User request:"""

    full_prompt = f"{system_prompt}\n{prompt}"

    try:
        model = get_model(model_name)
        response = model.generate(full_prompt)

        if not response:
            return None

        logger.debug(f"Local model response: {response}")

        # Try to parse JSON response
        # Handle case where response might have extra text around JSON
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]  # Remove ```json
        if response.startswith("```"):
            response = response[3:]  # Remove ```
        if response.endswith("```"):
            response = response[:-3]  # Remove ```

        # Strip any leading/trailing whitespace that might remain
        response = response.strip()

        logger.debug(f"Cleaned response: {response}")

        # Check if response is JSON (command translation) or conversational text
        try:
            data = json.loads(response)
            # It's JSON - check if it has command/explanation structure
            if isinstance(data, dict) and ("command" in data or "explanation" in data):
                command = data.get("command", "").strip()
                explanation = data.get("explanation", "").strip()

                if command and explanation:
                    return Translation(command=command, explanation=explanation)
            # If JSON but not command format, might be conversational response
            # Fall through to handle as conversational
        except (json.JSONDecodeError, ValueError):
            # Not JSON - this is likely a conversational response
            # Check if it looks like a command request that should have been JSON
            if any(
                word in response.lower()
                for word in ["command", "run", "execute", "list", "show", "find"]
            ):
                # Might be a description of a command - try to extract
                logger.debug("Response appears to describe a command but isn't JSON format")
            else:
                # This is a conversational response - return it as an echo command
                logger.debug("Response appears to be conversational, returning as echo command")
                return Translation(
                    command=f'echo """{response}"""',
                    explanation="Conversational response - providing direct answer to user's question",
                    needs_execution=False,  # Conversational response, no execution needed
                )

        # If we got here, the response wasn't in expected format
        # For conversational responses that don't match patterns, return them as-is
        if not response.startswith("{") and '"command"' not in response:
            return Translation(
                command=f'echo """{response}"""',
                explanation="Direct response to user's query",
                needs_execution=False,  # Conversational response, no execution needed
            )

        # If we still have the response but it's not handled, return None
        return None
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Local model translation failed: {e}")

    return None
