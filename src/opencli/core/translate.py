from __future__ import annotations

import re
import json
import logging
import platform
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from opencli.models.openrouter import translate_command_with_openrouter
from opencli.models.inference import get_model
from opencli.core.context_provider import ContextProvider
from opencli.tools.system_info import get_system_info

logger = logging.getLogger(__name__)

@dataclass
class Translation:
    command: str
    explanation: str


COMMON_PATTERNS: List[Tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"list\s+all\s+python\s+files\s+modified\s+(today|in\s+the\s+last\s+day)\b", re.I),
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
        re.compile(r"(show|tell|what|give|provide)(\s+is)?\s+(me\s+)?(the\s+)?(conversation\s+)?(history|memory|context)\b", re.I),
        'echo "Use the memory summary feature"',
        "Provide a summary of the conversation history and memory.",
    ),
]





def generate_memory_summary_with_llm(context_provider: ContextProvider, prompt: str) -> Optional[Translation]:
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
        from opencli.models.openrouter import chat_completion
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes conversation history and memory."},
            {"role": "user", "content": summary_prompt}
        ]
        
        response = chat_completion(messages, temperature=0.3, max_tokens=500)
        if response:
            # Handle echo model response
            if response.startswith("Echo:"):
                # Use the context summary directly
                return Translation(
                    command=f"echo \"\"\"{context_summary}\"\"\"", 
                    explanation="Displaying conversation history and memory summary"
                )
            # Return a command that will display the summary
            return Translation(
                command=f"echo \"\"\"{response}\"\"\"", 
                explanation="Displaying conversation history and memory summary"
            )
        
        # Fallback to local model
        model = get_model("default")
        if model:
            response = model.generate(summary_prompt)
            if response:
                # Handle echo model response
                if response.startswith("Echo:"):
                    # Use the context summary directly
                    return Translation(
                        command=f"echo \"\"\"{context_summary}\"\"\"", 
                        explanation="Displaying conversation history and memory summary"
                    )
                return Translation(
                    command=f"echo \"\"\"{response}\"\"\"", 
                    explanation="Displaying conversation history and memory summary"
                )
    except Exception as e:
        logger.warning(f"Failed to generate memory summary with LLM: {e}")
    
    # Fallback to simple context summary
    context_summary = context_provider.generate_memory_summary()
    return Translation(
        command=f"echo \"\"\"{context_summary}\"\"\"", 
        explanation="Displaying conversation history and memory summary"
    )


def translate_to_command(prompt: str, context_provider: Optional[ContextProvider] = None) -> Optional[Translation]:
    text = prompt.strip()
    
    # First try pattern matching
    for pattern, template, explanation in COMMON_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        
        # Special handling for memory/history requests
        if re.search(r"(show|tell|what|give|provide)(\s+is)?\s+(me\s+)?(the\s+)?(conversation\s+)?(history|memory|context)\b", text, re.I):
            if context_provider:
                # Generate memory summary using LLM
                return generate_memory_summary_with_llm(context_provider, prompt)
            else:
                command = template
                if "{size}" in template and m.groups():
                    size = m.group(1)
                    command = template.format(size=size)
                
                # Adapt command for Windows if needed
                if platform.system() == "Windows":
                    command = adapt_command_for_windows(command)
                    
                return Translation(command=command, explanation=explanation)
        
        command = template
        if "{size}" in template and m.groups():
            size = m.group(1)
            command = template.format(size=size)
        
        # Adapt command for Windows if needed
        command = adapt_command_for_windows(command)
            
        return Translation(command=command, explanation=explanation)
    
    # If pattern matching fails, try LLM-based translation
    return translate_with_llm(prompt, context_provider)


def adapt_command_for_windows(command: str, system_info: Optional[str] = None) -> str:
    """Adapt Unix commands for Windows."""
    # If system_info is not provided, detect it
    if system_info is None:
        from opencli.tools.system_info import get_system_info
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


def translate_with_llm(prompt: str, context_provider: Optional[ContextProvider] = None) -> Optional[Translation]:
    """Translate natural language to command using LLM."""
    try:
        # Try OpenRouter first
        translation = translate_with_openrouter(prompt, context_provider)
        if translation:
            command = translation["command"]
            # Adapt command for Windows if needed
            command = adapt_command_for_windows(command)
            return Translation(command=command, explanation=translation["explanation"])
            
        # Fallback to local model
        translation = translate_with_local_model(prompt, context_provider)
        if translation:
            command = translation.command
            # Adapt command for Windows if needed
            command = adapt_command_for_windows(command)
            return Translation(command=command, explanation=translation.explanation)
            
    except Exception as e:
        logger.warning(f"LLM translation failed: {e}")
    
    return None


def translate_with_openrouter(prompt: str, context_provider: Optional[ContextProvider] = None) -> Optional[Dict[str, str]]:
    """Translate using OpenRouter API."""
    from opencli.models.openrouter import translate_command_with_openrouter as openrouter_translate
    
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
        return translate_command_with_openrouter_context_aware(context_messages, system_info)
    
    # Fallback to original implementation
    return openrouter_translate(prompt)


def translate_command_with_openrouter_context_aware(messages: List[Dict[str, str]], system_info: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Translate using OpenRouter API with context awareness."""
    from opencli.models.openrouter import chat_completion
    
    # Use provided system_info or get it from the system
    if system_info is None:
        system_info = get_system_info()
    
    system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
You have access to conversation history and user preferences to provide better responses.
Respond ONLY with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

User request:"""
    
    # Prepend system prompt to messages
    full_messages = [{"role": "system", "content": system_prompt}]
    
    # Add context messages, but make sure we don't duplicate system messages
    for msg in messages:
        # Skip system messages that contain example responses to avoid duplication
        # But keep system information messages as they contain valuable context
        if msg["role"] != "system" or "Example response" not in msg["content"]:
            full_messages.append(msg)
    
    response = chat_completion(full_messages, temperature=0.1, max_tokens=256)
    if not response:
        return None
        
    try:
        # Clean up the response to handle markdown code blocks
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove ```
        
        # Parse JSON response
        data = json.loads(cleaned_response)
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        
        if command and explanation:
            return {"command": command, "explanation": explanation}
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse OpenRouter response as JSON: {response}")
        return None
    
    return None


def translate_with_local_model(prompt: str, context_provider: Optional[ContextProvider] = None) -> Optional[Translation]:
    """Translate using local model."""
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

Respond ONLY with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

User request:"""
    else:
        system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
Respond ONLY with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

User request:"""
    
    full_prompt = f"{system_prompt}\n{prompt}"
    
    try:
        model = get_model("default")
        response = model.generate(full_prompt)
        
        if not response:
            return None
            
        logger.info(f"Local model response: {response}")
            
        # Try to parse JSON response
        # Handle case where response might have extra text around JSON
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]  # Remove ```json
        if response.startswith("```"):
            response = response[3:]  # Remove ```
        if response.endswith("```"):
            response = response[:-3]  # Remove ```
        
        logger.info(f"Cleaned response: {response}")
        
        data = json.loads(response)
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        
        if command and explanation:
            return Translation(command=command, explanation=explanation)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Local model translation failed: {e}")
    
    return None
