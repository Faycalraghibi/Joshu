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
                return json.dumps(
                    {
                        "command": 'echo "For code generation, please use the code command: joshu code \\"your request\\" or configure your API key for cloud models"',
                        "explanation": "This appears to be a code generation request. Use the 'code' command or configure your API key for better results.",
                    }
                )

            api_status = self._check_api_configuration()
            if api_status != "ok":
                return json.dumps(
                    {
                        "command": f'echo "API configuration issue: {api_status}. Please check your .env file or configure local model API."',
                        "explanation": "API access is required for complex requests but not properly configured.",
                    }
                )
            else:
                return json.dumps(
                    {
                        "command": 'echo "Direct API access required for complex requests. Please configure your API key or use simpler commands."',
                        "explanation": f"This request requires API access to process: '{user_request[:50]}...'. Please configure your API key or try a simple command like 'ls' or 'pwd'.",
                    }
                )
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
                return json.dumps(
                    {
                        "command": 'echo "For code generation, please use the code command: joshu code \\"your request\\" or configure your API key for cloud models"',
                        "explanation": "This appears to be a code generation request. Use the 'code' command or configure your API key for better results.",
                    }
                )

            api_status = self._check_api_configuration()
            if api_status != "ok":
                return json.dumps(
                    {
                        "command": f'echo "API configuration issue: {api_status}. Please check your .env file or configure local model API."',
                        "explanation": "API access is required for complex requests but not properly configured.",
                    }
                )
            else:
                return json.dumps(
                    {
                        "command": 'echo "Direct API access required for complex requests. Please configure your API key or use simpler commands."',
                        "explanation": f"This request requires API access to process: '{prompt[:50]}...'. Please configure your API key or try a simple command like 'ls' or 'pwd'.",
                    }
                )

    def _handle_conversational_prompt(self, prompt: str) -> Optional[str]:
        """Handle common conversational prompts locally."""
        prompt_lower = prompt.lower().strip()

        if prompt_lower in ["hi", "hello", "hey", "greetings"]:
            return json.dumps(
                {
                    "command": "echo \"Hello! I'm Joshu Assistant. I can help you with shell commands and code generation. Try asking me to 'ls' or 'give me code for binary search in python'\"",
                    "explanation": "Friendly greeting response",
                }
            )

        if prompt_lower in ["thanks", "thank you", "thx"]:
            return json.dumps(
                {
                    "command": 'echo "You\'re welcome! Let me know if you need help with anything else."',
                    "explanation": "Polite response to thanks",
                }
            )

        if prompt_lower in ["how are you", "how are you?", "how do you do"]:
            return json.dumps(
                {
                    "command": "echo \"I'm doing well, thank you for asking! I'm here to help you with CLI commands and code generation.\"",
                    "explanation": "Standard response to 'how are you'",
                }
            )

        if prompt_lower in ["help", "help me"]:
            return json.dumps(
                {
                    "command": "echo \"Try asking me to perform shell commands like 'ls' or 'pwd', or ask for code generation like 'give me code for binary search in python'. For more options, type '/help' in interactive mode.\"",
                    "explanation": "Helpful guidance for using Joshu",
                }
            )

        return None

    def _is_code_generation_request(self, prompt: str) -> bool:
        """Check if the prompt is likely a code generation request."""
        prompt_lower = prompt.lower()
        code_keywords = [
            "code",
            "program",
            "script",
            "function",
            "class",
            "method",
            "algorithm",
            "binary search",
            "sort",
            "python",
            "javascript",
            "java",
            "c++",
            "c#",
            "go",
            "rust",
            "php",
            "ruby",
            "swift",
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
            "mkdir",
            "rm",
            "cp",
            "mv",
            "echo",
            "cd",
            "git",
            "python",
            "pip",
            "npm",
            "docker",
            "kubectl",
            "terraform",
            "aws",
            "gcloud",
            "az",
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
        if re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*(\s+.*)?$", prompt_stripped):
            words = prompt_stripped.split()
            if len(words) > 0:
                # Common commands that can be recognized
                common_commands = {
                    "ls",
                    "dir",
                    "pwd",
                    "cd",
                    "cat",
                    "type",
                    "find",
                    "grep",
                    "mkdir",
                    "rm",
                    "del",
                    "cp",
                    "copy",
                    "mv",
                    "move",
                    "echo",
                    "git",
                    "python",
                    "pip",
                    "npm",
                    "docker",
                    "kubectl",
                    "terraform",
                    "aws",
                    "gcloud",
                    "az",
                }
                if words[0].lower() in common_commands:
                    return prompt_stripped

        return ""

    def _generate_explanation_for_command(self, command: str) -> str:
        """Generate an explanation for a command."""
        command_lower = command.lower().strip()
        is_windows = self._is_windows()

        # Direct command mappings
        command_explanations = {
            "dir": "List all files and directories in the current directory",
            "ls": "List files and directories",
            "ls -la": "List all files and directories in the current directory with details",
            "pwd": "Print working directory",
            "cd": "Show current directory path" if is_windows else "Print working directory",
            "type": "Display the contents of a file",
            "cat": "Display the contents of a file",
            "clear": "Clear the terminal screen",
            "cls": "Clear the terminal screen",
            "exit": "Exit the current shell or program",
            "help": "Display help information",
            "man": "Display manual page for a command",
            "history": "Display command history",
            "whoami": "Display current user name",
            "date": "Display current date and time",
            "uptime": "Show how long the system has been running",
            "df": "Display disk space usage",
            "du": "Display file space usage",
            "ps": "Display running processes",
            "top": "Display and update sorted information about processes",
            "kill": "Terminate a process",
            "chmod": "Change file permissions",
            "chown": "Change file owner and group",
            "tar": "Create and manipulate tar archives",
            "zip": "Package and compress files",
            "unzip": "Extract compressed files",
            "ssh": "Connect to a remote machine using SSH",
            "scp": "Securely copy files between hosts",
            "wget": "Download files from the web",
            "curl": "Transfer data from or to a server",
            "ping": "Send ICMP ECHO_REQUEST packets to network hosts",
            "ipconfig": (
                "Display IP configuration"
                if is_windows
                else "Show and manipulate routing and network devices"
            ),
            "ifconfig": "Configure network interfaces",
            "netstat": "Display network connections",
            "sudo": "Execute a command as another user",
            "su": "Switch user",
            "passwd": "Change user password",
            "reboot": "Restart the system",
            "shutdown": "Shutdown or restart the system",
            "mount": "Mount a filesystem",
            "umount": "Unmount a filesystem",
            "find": "Search for files in a directory hierarchy",
            "locate": "Find files by name",
            "which": "Locate a command",
            "where": "Locate a command" if is_windows else "Locate a command",
        }

        # Check for exact command matches
        if command_lower in command_explanations:
            return command_explanations[command_lower]

        # Command prefix patterns and their explanations
        command_patterns = [
            # File operations
            ("cd ", lambda cmd: f"Change directory to: {cmd[3:]}"),
            (
                "type ",
                lambda cmd: f"Display the contents of file: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "cat ",
                lambda cmd: f"Display the contents of file: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "touch ",
                lambda cmd: f"Create empty file or update timestamp: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "mkdir ",
                lambda cmd: f"Create directory: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "rmdir ",
                lambda cmd: f"Remove empty directory: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "del ",
                lambda cmd: f"Delete file: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "rm ",
                lambda cmd: f"Remove file or directory: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "copy ",
                lambda cmd: f"Copy files: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "cp ",
                lambda cmd: f"Copy files: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "move ",
                lambda cmd: f"Move files: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "mv ",
                lambda cmd: f"Move or rename files: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "rename ",
                lambda cmd: f"Rename file: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            # Text processing
            ("echo ", lambda cmd: "Display a message or redirect output to a file"),
            ("print ", lambda cmd: "Display a message"),
            (
                "findstr ",
                lambda cmd: f"Search for pattern in files: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "grep ",
                lambda cmd: f"Search for pattern in files: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "sed ",
                lambda cmd: f"Stream editor for filtering and transforming text: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            (
                "awk ",
                lambda cmd: f"Pattern scanning and processing language: {cmd.split(None, 1)[1] if len(cmd.split()) > 1 else ''}",
            ),
            ("sort ", lambda cmd: "Sort lines of text files"),
            ("uniq ", lambda cmd: "Remove duplicate lines from a sorted file"),
            ("wc ", lambda cmd: "Count lines, words, and characters in a file"),
            ("head ", lambda cmd: "Output the first part of files"),
            ("tail ", lambda cmd: "Output the last part of files"),
            ("cut ", lambda cmd: "Remove sections from each line of files"),
            ("paste ", lambda cmd: "Merge lines of files"),
            # Version control
            ("git ", lambda cmd: "Execute Git version control command"),
            ("svn ", lambda cmd: "Execute Subversion version control command"),
            ("hg ", lambda cmd: "Execute Mercurial version control command"),
            # Package managers
            ("pip ", lambda cmd: "Manage Python packages"),
            ("conda ", lambda cmd: "Manage Conda packages and environments"),
            ("npm ", lambda cmd: "Manage Node.js packages"),
            ("yarn ", lambda cmd: "Manage Node.js packages"),
            ("apt-get ", lambda cmd: "Manage Debian/Ubuntu packages"),
            ("apt ", lambda cmd: "Manage Debian/Ubuntu packages"),
            ("yum ", lambda cmd: "Manage RPM packages"),
            ("dnf ", lambda cmd: "Manage RPM packages"),
            ("brew ", lambda cmd: "Manage macOS packages"),
            ("choco ", lambda cmd: "Manage Windows packages"),
            # Programming languages
            ("python ", lambda cmd: "Execute Python script or command"),
            ("python3 ", lambda cmd: "Execute Python 3 script or command"),
            ("node ", lambda cmd: "Execute Node.js script"),
            ("java ", lambda cmd: "Execute Java program"),
            ("javac ", lambda cmd: "Compile Java source code"),
            ("gcc ", lambda cmd: "Compile C source code"),
            ("g++ ", lambda cmd: "Compile C++ source code"),
            ("go ", lambda cmd: "Execute Go program"),
            ("ruby ", lambda cmd: "Execute Ruby script"),
            ("perl ", lambda cmd: "Execute Perl script"),
            ("php ", lambda cmd: "Execute PHP script"),
            ("rustc ", lambda cmd: "Compile Rust source code"),
            ("cargo ", lambda cmd: "Manage Rust projects"),
            # Containerization and orchestration
            ("docker ", lambda cmd: "Manage Docker containers and images"),
            ("docker-compose ", lambda cmd: "Define and run multi-container Docker applications"),
            ("kubectl ", lambda cmd: "Manage Kubernetes clusters"),
            ("helm ", lambda cmd: "Manage Kubernetes applications"),
            # Infrastructure as code
            ("terraform ", lambda cmd: "Manage infrastructure as code with Terraform"),
            ("ansible ", lambda cmd: "Automate configuration management"),
            ("puppet ", lambda cmd: "Manage configuration"),
            ("chef ", lambda cmd: "Manage configuration"),
            # Cloud providers
            ("aws ", lambda cmd: "Execute AWS CLI command"),
            ("gcloud ", lambda cmd: "Execute Google Cloud CLI command"),
            ("az ", lambda cmd: "Execute Azure CLI command"),
            ("oci ", lambda cmd: "Execute Oracle Cloud CLI command"),
            ("ibmcloud ", lambda cmd: "Execute IBM Cloud CLI command"),
            # Database
            ("mysql ", lambda cmd: "Execute MySQL command"),
            ("psql ", lambda cmd: "Execute PostgreSQL command"),
            ("mongo ", lambda cmd: "Execute MongoDB command"),
            ("redis-cli ", lambda cmd: "Execute Redis command"),
            ("sqlite3 ", lambda cmd: "Execute SQLite command"),
            # Network
            ("telnet ", lambda cmd: "Communicate with another host using TELNET protocol"),
            ("ftp ", lambda cmd: "File Transfer Protocol client"),
            ("sftp ", lambda cmd: "Secure File Transfer Protocol client"),
            ("rsync ", lambda cmd: "Remote file synchronization"),
            ("nslookup ", lambda cmd: "Query Internet name servers interactively"),
            ("dig ", lambda cmd: "DNS lookup utility"),
            ("traceroute ", lambda cmd: "Print the route packets trace to network host"),
            ("route ", lambda cmd: "Show and manipulate IP routing table"),
            # System monitoring
            ("iostat ", lambda cmd: "Report CPU and I/O statistics"),
            ("vmstat ", lambda cmd: "Report virtual memory statistics"),
            ("netstat ", lambda cmd: "Display network connections"),
            ("lsof ", lambda cmd: "List open files"),
            ("free ", lambda cmd: "Display amount of free and used memory in the system"),
            # Compression and archiving
            ("gzip ", lambda cmd: "Compress or expand files"),
            ("gunzip ", lambda cmd: "Compress or expand files"),
            ("bzip2 ", lambda cmd: "Compress or expand files"),
            ("bunzip2 ", lambda cmd: "Compress or expand files"),
            ("xz ", lambda cmd: "Compress or expand files"),
            ("unxz ", lambda cmd: "Compress or expand files"),
            ("zip ", lambda cmd: "Package and compress files"),
            ("unzip ", lambda cmd: "Extract compressed files"),
            ("tar ", lambda cmd: "Create and manipulate tar archives"),
            ("7z ", lambda cmd: "Compress or extract files with 7-Zip"),
            # Editors
            ("vi ", lambda cmd: "Open file in Vi editor"),
            ("vim ", lambda cmd: "Open file in Vim editor"),
            ("nano ", lambda cmd: "Open file in Nano editor"),
            ("emacs ", lambda cmd: "Open file in Emacs editor"),
            ("code ", lambda cmd: "Open file in Visual Studio Code"),
            ("notepad ", lambda cmd: "Open file in Notepad"),
        ]

        # Check for command pattern matches
        for prefix, explanation_func in command_patterns:
            if command_lower.startswith(prefix):
                return explanation_func(command)

        # If no match found, return a generic explanation
        return f"Execute command: {command}"
