from __future__ import annotations

import json
import re
import platform
from typing import Any, Optional

from .llm_interface import LLM


class EchoModel(LLM):
    def generate(self, prompt: str, **kwargs: Any) -> str:
        # Check if this is a prompt with context information
        # If so, extract just the user request part
        if "\nUser request:\n" in prompt:
            user_request = prompt.split("\nUser request:\n")[-1].strip()
            # Handle common conversational prompts locally
            response = self._handle_conversational_prompt(user_request)
            if response:
                return response
            # Try to extract a command from the user request
            command = self._extract_command_from_prompt(user_request)
            if command:
                explanation = self._generate_explanation_for_command(command)
                # Return proper JSON response
                return json.dumps({
                    "command": command,
                    "explanation": explanation
                })
            else:
                # For non-command requests, provide a helpful message
                return json.dumps({
                    "command": "echo \"Direct API access required\"",
                    "explanation": f"This request requires API access to process: '{user_request[:50]}...'. Please configure your API key or try a simple command like 'ls' or 'pwd'."
                })
        else:
            # Handle regular prompts
            # Handle common conversational prompts locally
            response = self._handle_conversational_prompt(prompt)
            if response:
                return response
            command = self._extract_command_from_prompt(prompt)
            if command:
                explanation = self._generate_explanation_for_command(command)
                # Return proper JSON response
                return json.dumps({
                    "command": command,
                    "explanation": explanation
                })
            else:
                # Fallback to echo with a proper message
                return f"Echo: {prompt}"
    
    def _handle_conversational_prompt(self, prompt: str) -> Optional[str]:
        """Handle common conversational prompts locally."""
        prompt_lower = prompt.lower().strip()
        
        # Handle greetings
        if prompt_lower in ["hi", "hello", "hey", "greetings"]:
            return json.dumps({
                "command": "echo \"Hello! I'm Joshu Assistant. I can help you with shell commands and code generation. Try asking me to 'ls' or 'give me code for binary search in python'\"",
                "explanation": "Friendly greeting response"
            })
        
        # Handle thanks
        if prompt_lower in ["thanks", "thank you", "thx"]:
            return json.dumps({
                "command": "echo \"You're welcome! Let me know if you need help with anything else.\"",
                "explanation": "Polite response to thanks"
            })
        
        # Handle common questions
        if prompt_lower in ["how are you", "how are you?", "how do you do"]:
            return json.dumps({
                "command": "echo \"I'm doing well, thank you for asking! I'm here to help you with CLI commands and code generation.\"",
                "explanation": "Standard response to 'how are you'"
            })
        
        # Handle help requests
        if prompt_lower in ["help", "help me"]:
            return json.dumps({
                "command": "echo \"Try asking me to perform shell commands like 'ls' or 'pwd', or ask for code generation like 'give me code for binary search in python'. For more options, type '/help' in interactive mode.\"",
                "explanation": "Helpful guidance for using Joshu"
            })
        
        # No special handling needed
        return None
    
    def _is_windows(self) -> bool:
        """Check if we're running on Windows."""
        return platform.system().lower() == "windows"
    
    def _extract_command_from_prompt(self, prompt: str) -> str:
        """Extract a command from the prompt."""
        prompt_lower = prompt.lower().strip()
        is_windows = self._is_windows()
        
        # Handle common shell commands
        if prompt_lower == "ls":
            return "dir" if is_windows else "ls -la"
        elif prompt_lower.startswith("ls "):
            return prompt.replace("ls", "dir") if is_windows else prompt
        elif prompt_lower == "pwd":
            return "cd" if is_windows else "pwd"
        elif prompt_lower == "cat":
            return "type" if is_windows else "cat"
        elif prompt_lower.startswith("cat "):
            return prompt.replace("cat", "type") if is_windows else prompt
        elif prompt_lower.startswith("find "):
            return prompt.replace("find", "dir /s") if is_windows else prompt
        elif prompt_lower.startswith("grep "):
            return f"findstr {prompt_lower[5:]}" if is_windows else prompt
        elif prompt_lower.startswith("mkdir "):
            return prompt
        elif prompt_lower.startswith("rm "):
            return f"del {prompt_lower[3:]}" if is_windows else prompt
        elif prompt_lower.startswith("cp "):
            return f"copy {prompt_lower[3:]}" if is_windows else prompt
        elif prompt_lower.startswith("mv "):
            return f"move {prompt_lower[3:]}" if is_windows else prompt
        elif prompt_lower.startswith("echo "):
            return prompt
        elif prompt_lower.startswith("cd "):
            return prompt
        elif prompt_lower == "cd":
            return "cd" if is_windows else "pwd"
        elif prompt_lower.startswith("git "):
            return prompt
        elif prompt_lower.startswith("python "):
            return prompt
        elif prompt_lower.startswith("pip "):
            return prompt
        elif prompt_lower.startswith("npm "):
            return prompt
        elif prompt_lower.startswith("docker "):
            return prompt
        elif prompt_lower.startswith("kubectl "):
            return prompt
        elif prompt_lower.startswith("terraform "):
            return prompt
        elif prompt_lower.startswith("aws "):
            return prompt
        elif prompt_lower.startswith("gcloud "):
            return prompt
        elif prompt_lower.startswith("az "):
            return prompt
        
        # If it looks like a command (single word that starts with a letter, or word followed by arguments)
        # but not sentences with multiple words that don't look like commands
        prompt_stripped = prompt.strip()
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*(\s+.*)?$', prompt_stripped):
            # Additional check: if it's a single word, it should be a common command
            words = prompt_stripped.split()
            if len(words) == 1:
                # Single word - check if it's a common command
                common_commands = {
                    'ls', 'dir', 'pwd', 'cd', 'cat', 'type', 'find', 'grep', 'mkdir', 'rm', 'del', 
                    'cp', 'copy', 'mv', 'move', 'echo', 'git', 'python', 'pip', 'npm', 'docker',
                    'kubectl', 'terraform', 'aws', 'gcloud', 'az'
                }
                if words[0].lower() in common_commands:
                    return prompt_stripped
                else:
                    # Not a recognized command
                    return ""
            else:
                # Multiple words - check if the first word is a common command
                common_commands = {
                    'ls', 'dir', 'pwd', 'cd', 'cat', 'type', 'find', 'grep', 'mkdir', 'rm', 'del', 
                    'cp', 'copy', 'mv', 'move', 'echo', 'git', 'python', 'pip', 'npm', 'docker',
                    'kubectl', 'terraform', 'aws', 'gcloud', 'az'
                }
                if words[0].lower() in common_commands:
                    return prompt_stripped
                else:
                    # First word is not a recognized command
                    return ""
        
        # Return empty string if we can't extract a command
        return ""
    
    def _generate_explanation_for_command(self, command: str) -> str:
        """Generate an explanation for a command."""
        command_lower = command.lower().strip()
        is_windows = self._is_windows()
        
        if command_lower == "dir" or command_lower == "ls -la":
            return "List all files and directories in the current directory"
        elif command_lower.startswith("dir ") or command_lower.startswith("ls "):
            return f"List files and directories with the specified options: {command}"
        elif command_lower == "cd":
            return "Show current directory path" if is_windows else "Print working directory"
        elif command_lower.startswith("cd "):
            return f"Change directory to: {command[3:]}"
        elif command_lower == "type" or command_lower == "cat":
            return "Display the contents of a file"
        elif command_lower.startswith("type ") or command_lower.startswith("cat "):
            return f"Display the contents of file: {command.split()[1]}"
        elif command_lower.startswith("findstr ") or command_lower.startswith("grep "):
            return f"Search for pattern in files: {command.split(None, 1)[1]}"
        elif command_lower.startswith("mkdir "):
            return f"Create directory: {command[6:]}"
        elif command_lower.startswith("del ") or command_lower.startswith("rm "):
            return f"Delete file: {command.split(None, 1)[1]}"
        elif command_lower.startswith("copy ") or command_lower.startswith("cp "):
            return f"Copy files: {command.split(None, 1)[1]}"
        elif command_lower.startswith("move ") or command_lower.startswith("mv "):
            return f"Move files: {command.split(None, 1)[1]}"
        elif command_lower.startswith("echo "):
            return "Display a message or redirect output to a file"
        elif command_lower.startswith("git "):
            return "Execute Git version control command"
        elif command_lower.startswith("python "):
            return "Execute Python script or command"
        elif command_lower.startswith("pip "):
            return "Manage Python packages"
        elif command_lower.startswith("npm "):
            return "Manage Node.js packages"
        elif command_lower.startswith("docker "):
            return "Manage Docker containers and images"
        elif command_lower.startswith("kubectl "):
            return "Manage Kubernetes clusters"
        elif command_lower.startswith("terraform "):
            return "Manage infrastructure as code with Terraform"
        elif command_lower.startswith("aws "):
            return "Execute AWS CLI command"
        elif command_lower.startswith("gcloud "):
            return "Execute Google Cloud CLI command"
        elif command_lower.startswith("az "):
            return "Execute Azure CLI command"
        else:
            return f"Execute command: {command}"