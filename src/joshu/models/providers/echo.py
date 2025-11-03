"""Echo model provider implementation (fallback/offline mode)."""

from __future__ import annotations

import json
import logging
import os
import platform
import re
from typing import Any, Dict, Optional

from ..base import LLM, ModelProvider
from ..config import ModelConfig

logger = logging.getLogger(__name__)


class EchoProvider(LLM, ModelProvider):
    """Provider for echo model (fallback when no other models are available)."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize echo provider.
        
        Args:
            config: Optional configuration dictionary
        """
        config = config or {}
        # Initialize ModelProvider first
        ModelProvider.__init__(self, name="echo", config=config)
        self._initialized = True
        self._available = True
    
    def initialize(self) -> bool:
        """Echo provider is always available."""
        self._initialized = True
        self._available = True
        return True
    
    def is_available(self) -> bool:
        """Echo provider is always available."""
        return True
    
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """Generate response using echo model (pattern matching and simple logic)."""
        # Check if this is a prompt with context information
        if "\nUser request:\n" in prompt:
            user_request = prompt.split("\nUser request:\n")[-1].strip()
            response = self._handle_conversational_prompt(user_request)
            if response:
                return response
            
            command = self._extract_command_from_prompt(user_request)
            if command:
                explanation = self._generate_explanation_for_command(command)
                return json.dumps({"command": command, "explanation": explanation})
            
            # Handle complex requests
            if self._is_code_generation_request(user_request):
                return json.dumps({
                    "command": 'echo "For code generation, please use the code command: joshu code \\"your request\\" or configure your API key for cloud models"',
                    "explanation": "This appears to be a code generation request. Use the 'code' command or configure your API key for better results."
                })
            
            api_status = self._check_api_configuration()
            if api_status != "ok":
                return json.dumps({
                    "command": f'echo "API configuration issue: {api_status}. Please check your .env file or use local models."',
                    "explanation": "API access is required for complex requests but not properly configured."
                })
            else:
                return json.dumps({
                    "command": 'echo "Direct API access required for complex requests. Please configure your API key or use simpler commands."',
                    "explanation": f"This request requires API access to process: '{user_request[:50]}...'. Please configure your API key or try a simple command like 'ls' or 'pwd'."
                })
        else:
            # Handle regular prompts
            response = self._handle_conversational_prompt(prompt)
            if response:
                return response
            
            command = self._extract_command_from_prompt(prompt)
            if command:
                explanation = self._generate_explanation_for_command(command)
                return json.dumps({"command": command, "explanation": explanation})
            
            if self._is_code_generation_request(prompt):
                return json.dumps({
                    "command": 'echo "For code generation, please use the code command: joshu code \\"your request\\" or configure your API key for cloud models"',
                    "explanation": "This appears to be a code generation request. Use the 'code' command or configure your API key for better results."
                })
            
            api_status = self._check_api_configuration()
            if api_status != "ok":
                return json.dumps({
                    "command": f'echo "API configuration issue: {api_status}. Please check your .env file or use local models."',
                    "explanation": "API access is required for complex requests but not properly configured."
                })
            else:
                return json.dumps({
                    "command": 'echo "Direct API access required for complex requests. Please configure your API key or use simpler commands."',
                    "explanation": f"This request requires API access to process: '{prompt[:50]}...'. Please configure your API key or try a simple command like 'ls' or 'pwd'."
                })
    
    def _handle_conversational_prompt(self, prompt: str) -> Optional[str]:
        """Handle common conversational prompts locally."""
        prompt_lower = prompt.lower().strip()
        
        if prompt_lower in ["hi", "hello", "hey", "greetings"]:
            return json.dumps({
                "command": "echo \"Hello! I'm Joshu Assistant. I can help you with shell commands and code generation. Try asking me to 'ls' or 'give me code for binary search in python'\"",
                "explanation": "Friendly greeting response"
            })
        
        if prompt_lower in ["thanks", "thank you", "thx"]:
            return json.dumps({
                "command": "echo \"You're welcome! Let me know if you need help with anything else.\"",
                "explanation": "Polite response to thanks"
            })
        
        if prompt_lower in ["how are you", "how are you?", "how do you do"]:
            return json.dumps({
                "command": "echo \"I'm doing well, thank you for asking! I'm here to help you with CLI commands and code generation.\"",
                "explanation": "Standard response to 'how are you'"
            })
        
        if prompt_lower in ["help", "help me"]:
            return json.dumps({
                "command": "echo \"Try asking me to perform shell commands like 'ls' or 'pwd', or ask for code generation like 'give me code for binary search in python'. For more options, type '/help' in interactive mode.\"",
                "explanation": "Helpful guidance for using Joshu"
            })
        
        return None
    
    def _is_code_generation_request(self, prompt: str) -> bool:
        """Check if the prompt is likely a code generation request."""
        prompt_lower = prompt.lower()
        code_keywords = [
            "code", "program", "script", "function", "class", "method", "algorithm",
            "binary search", "sort", "python", "javascript", "java", "c++", "c#",
            "go", "rust", "php", "ruby", "swift"
        ]
        return any(keyword in prompt_lower for keyword in code_keywords)
    
    def _check_api_configuration(self) -> str:
        """Check if API keys are properly configured."""
        if ModelConfig.has_any_api_key():
            return "ok"
        
        configured_model = os.getenv("OPENROUTER_MODEL") or "llama-3-8b"
        for cloud_model in ModelConfig.CLOUD_MODELS:
            if cloud_model in configured_model.lower():
                return f"API key missing for {cloud_model} model"
        
        return "no API keys configured"
    
    def _is_windows(self) -> bool:
        """Check if we're running on Windows."""
        return platform.system().lower() == "windows"
    
    def _extract_command_from_prompt(self, prompt: str) -> str:
        """Extract a command from the prompt."""
        prompt_lower = prompt.lower().strip()
        is_windows = self._is_windows()
        
        # Handle common shell commands
        command_mappings = {
            "ls": "dir" if is_windows else "ls -la",
            "pwd": "cd" if is_windows else "pwd",
            "cat": "type" if is_windows else "cat",
        }
        
        if prompt_lower in command_mappings:
            return command_mappings[prompt_lower]
        
        if prompt_lower.startswith("ls "):
            return prompt.replace("ls", "dir") if is_windows else prompt
        elif prompt_lower.startswith("cat "):
            return prompt.replace("cat", "type") if is_windows else prompt
        elif prompt_lower.startswith("find "):
            return prompt.replace("find", "dir /s") if is_windows else prompt
        elif prompt_lower.startswith("grep "):
            return f"findstr {prompt_lower[5:]}" if is_windows else prompt
        
        # Additional command mappings
        command_prefixes = {
            "mkdir", "rm", "cp", "mv", "echo", "cd", "git", "python",
            "pip", "npm", "docker", "kubectl", "terraform", "aws", "gcloud", "az"
        }
        
        for prefix in command_prefixes:
            if prompt_lower.startswith(f"{prefix} "):
                if prefix == "rm" and is_windows:
                    return f"del {prompt_lower[3:]}"
                elif prefix == "cp" and is_windows:
                    return f"copy {prompt_lower[3:]}"
                elif prefix == "mv" and is_windows:
                    return f"move {prompt_lower[3:]}"
                return prompt
        
        # Pattern matching for command-like inputs
        prompt_stripped = prompt.strip()
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*(\s+.*)?$', prompt_stripped):
            words = prompt_stripped.split()
            if len(words) == 1:
                common_commands = {
                    'ls', 'dir', 'pwd', 'cd', 'cat', 'type', 'find', 'grep',
                    'mkdir', 'rm', 'del', 'cp', 'copy', 'mv', 'move', 'echo',
                    'git', 'python', 'pip', 'npm', 'docker', 'kubectl',
                    'terraform', 'aws', 'gcloud', 'az'
                }
                if words[0].lower() in common_commands:
                    return prompt_stripped
            else:
                common_commands = {
                    'ls', 'dir', 'pwd', 'cd', 'cat', 'type', 'find', 'grep',
                    'mkdir', 'rm', 'del', 'cp', 'copy', 'mv', 'move', 'echo',
                    'git', 'python', 'pip', 'npm', 'docker', 'kubectl',
                    'terraform', 'aws', 'gcloud', 'az'
                }
                if words[0].lower() in common_commands:
                    return prompt_stripped
        
        return ""
    
    def _generate_explanation_for_command(self, command: str) -> str:
        """Generate an explanation for a command."""
        command_lower = command.lower().strip()
        is_windows = self._is_windows()
        
        explanations = {
            "dir": "List all files and directories in the current directory",
            "ls -la": "List all files and directories in the current directory",
            "cd": "Show current directory path" if is_windows else "Print working directory",
            "type": "Display the contents of a file",
            "cat": "Display the contents of a file",
        }
        
        if command_lower in explanations:
            return explanations[command_lower]
        
        if command_lower.startswith("cd "):
            return f"Change directory to: {command[3:]}"
        elif command_lower.startswith("type ") or command_lower.startswith("cat "):
            parts = command.split()
            if len(parts) > 1:
                return f"Display the contents of file: {parts[1]}"
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
        
        return f"Execute command: {command}"

