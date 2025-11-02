# Joshu 🤖

An AI-powered command-line assistant that transforms your terminal into an intelligent workspace. Joshu uses large language models to translate natural language into shell commands, generate code, execute tasks autonomously, and assist with complex workflows.

## 🌟 Features

### Core Capabilities

- **Natural Language to Commands**: Convert plain English to executable shell commands with safety validation
- **Interactive Multi-Mode Assistant**: Three distinct interaction modes (Agent, Ask, Plan) for different use cases
- **Code Generation & Editing**: Generate, explain, debug, and refactor code in multiple languages
- **Context-Aware Conversations**: Maintains conversation history and project context across sessions
- **Multi-Model Support**: Seamlessly switch between local and cloud-based LLMs
- **Session Management**: Track and manage multiple conversation sessions with persistent history
- **Safety-First Design**: Advanced command validation and sandbox mode for safe execution

### Interactive Modes

Joshu provides three powerful interaction modes:

#### 🤖 Agent Mode (Default)
Autonomous task execution from start to finish. Simply describe your goal and Joshu will:
- Generate a step-by-step execution plan
- Execute each command safely with validation
- Handle errors and ask for confirmation when needed
- Provide detailed execution summaries

#### 💬 Ask Mode
Direct Q&A without command execution. Perfect for:
- Getting explanations and information
- Understanding concepts and technologies
- Asking questions that don't require system actions

#### 📋 Plan Mode
Task planning without execution. Joshu will:
- Break down your goal into actionable steps
- Present a numbered list of commands
- Let you review and execute manually

### Advanced Features

- **Session Management**: Create, switch, and manage multiple conversation sessions
- **Conversation History**: Persistent, formatted conversation logs with timestamps and mode indicators
- **Command Safety**: Multi-level danger detection with user confirmation prompts
- **Sandbox Environment**: Safe code execution with optional sandbox mode
- **OpenRouter Integration**: Use powerful cloud models via OpenRouter API
- **Local Model Support**: Run Llama, Mistral, CodeLlama, and other models locally
- **Code Editing**: Edit files with LLM assistance, automatic backups, and validation
- **History Management**: Review, repeat, and explain past commands

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ (tested up to Python 3.13)
- 4GB+ RAM (8GB recommended for larger local models)
- CUDA-compatible GPU (optional, for faster local inference)

### Installation

```bash
# Clone the repository
git clone https://github.com/Faycacalraghibi/joshu-assistant.git
cd joshu-assistant

# Create a virtual environment (recommended)
python -m venv .joshuvenv
source .joshuvenv/bin/activate  # On Windows: .joshuvenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install LLM dependencies for local models
pip install -r requirements-llm.txt

# Install Joshu
pip install -e .
```

### Quick Installation Scripts

For automated setup, use the provided scripts:

**Windows (PowerShell):**
```powershell
.\clean_install-dev.ps1
```

**Linux/macOS (Bash):**
```bash
./clean_install-dev.sh
```

### First Run

```bash
# Start interactive mode
joshu run --interactive
# or
joshu interactive

# Execute a one-off command
joshu "list all python files modified today"

# Get help
joshu --help
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in your project root or home directory:

```bash
# Model Configuration
JOSHU_MODEL=llama-3-8b
JOSHU_USE_CLOUD=true

# OpenRouter API (optional, for cloud models)
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_SITE_TITLE=Joshu Assistant

# Model-Specific API Keys (optional)
DEEPSEEK_API_KEY=your_key
TONGYI_API_KEY=your_key
QWEN_API_KEY=your_key
KIMI_DEV_API_KEY=your_key
GLM_API_KEY=your_key

# Configuration Options
JOSHU_MEMORY_ENABLED=true
JOSHU_SANDBOX_ENABLED=true
JOSHU_LOG_LEVEL=INFO
JOSHU_MAX_CONTEXT=4096
```

### User Configuration File

Joshu supports user-level configuration at `~/.joshu/config.yaml`:

```yaml
# User configuration file at ~/.joshu/config.yaml
model: "llama-3-8b"
safety_mode: true
auto_execute: false
max_tokens: 4096
temperature: 0.1
history_size: 100
log_level: "INFO"
memory_enabled: true
sandbox_enabled: true
```

### CLI Configuration Management

Manage configuration directly from the command line:

```bash
# List all configuration options
joshu config --list

# Get a specific value
joshu config --get model

# Set configuration values
joshu config --set model=llama-3-70b
joshu config --set auto_execute=true

# Reset to defaults
joshu config --reset

# Edit configuration file directly
joshu config --edit
```

## 📖 Usage

### Command-Line Usage

```bash
# Execute a natural language command
joshu "find all files larger than 100MB"
joshu "create a backup of the project directory"
joshu "show disk usage sorted by size"

# Code generation and editing
joshu code "write a binary search function in Python"
joshu code "create a REST API with Flask"
joshu code --file app.py "add error handling to this file"
joshu code --file app.py "refactor this code to use async/await"

# Interactive mode
joshu run --interactive
joshu interactive --model llama-3-70b --verbose

# History and repetition
joshu history
joshu repeat-last
joshu explain-last

# Help and examples
joshu examples
joshu commands
joshu explain "git rebase"
```

### Interactive Mode Commands

When in interactive mode, you can use the following commands:

#### Mode Switching
- `/agent` - Switch to agent mode (autonomous execution)
- `/ask` - Switch to ask mode (Q&A without commands)
- `/plan` - Switch to plan mode (planning without execution)

#### Session Management
- `/session` - Show current session ID
- `/session list` - List all sessions
- `/session new` - Start a new session
- `/session end` - End current session and start a new one
- `/session switch <id>` - Switch to a session by ID
- `/session delete <id>` - Delete a session
- `/session help` - Show session management help

#### History and Configuration
- `/history` - Show command history
- `/clear` - Clear command history
- `/config` - Show/set configuration
- `/model` - Switch AI model
- `/help` - Show comprehensive help

#### Special Commands
- `!command` - Execute bash command directly
- `!!` - Repeat last bash command
- `!n` - Execute nth bash command from history
- `@file` - Inject file content
- `@@file` - Inject and execute file content
- `@file:n-m` - Inject lines n to m from file

### Keyboard Shortcuts (Interactive Mode)

- `Ctrl+R` - Reverse search through history
- `Ctrl+J` - Line navigation down
- `Ctrl+K` - Line navigation up
- `Ctrl+B` - Send command to background bash
- `Ctrl+C` - Interrupt current operation
- `Ctrl+D` - Exit interactive mode
- `Ctrl+L` - Clear screen
- `Ctrl+T` - Toggle command suggestions

### Vim Mode (Interactive Mode)

- `ESC` - Switch to NORMAL mode
- `i` - Switch to INSERT mode
- `h/j/k/l` - Left/Down/Up/Right navigation
- `w/b` - Word forward/backward
- `:` - Enter command mode

### Usage Examples

#### Agent Mode Example

```bash
joshu run --interactive
[AGENT] > create a Python project with Flask and SQLite

🎯 Goal: create a Python project with Flask and SQLite
📝 Generating execution plan...
🚀 Executing 4 step(s)...

[Step 1/4] Running: mkdir flask_project
✅ Command executed successfully

[Step 2/4] Running: cd flask_project
✅ Command executed successfully

[Step 3/4] Running: python -m venv venv
✅ Command executed successfully

[Step 4/4] Running: pip install flask sqlite3
✅ Command executed successfully

==================================================
📊 Execution Summary:
✅ Successfully executed: 4/4
==================================================
```

#### Ask Mode Example

```bash
[ASK] > how does virtual memory work?

💬 Virtual memory is a memory management technique that allows...
[Detailed explanation without generating commands]
```

#### Plan Mode Example

```bash
[PLAN] > set up a CI/CD pipeline

📋 Plan for: set up a CI/CD pipeline

1. Create .github/workflows directory
2. Create ci.yml workflow file
3. Configure build and test steps
4. Set up deployment steps
5. Configure environment variables

[Plan displayed - execute manually or switch to agent mode]
```

#### Code Generation Example

```bash
joshu code "write a REST API endpoint that returns user data from a database"

# Generated code will be displayed with explanations
```

## 🏗️ Architecture

```
joshu-assistant/
├── src/joshu/
│   ├── core/                    # Core functionality
│   │   ├── agent.py            # Main assistant logic (placeholder)
│   │   ├── code_editor.py      # Code generation and editing
│   │   ├── config.py           # Configuration management
│   │   ├── context.py          # Conversation context
│   │   ├── context_provider.py # Context and session management
│   │   ├── memory.py           # Memory system
│   │   ├── safety.py           # Command safety validation
│   │   └── translate.py        # Natural language translation
│   ├── models/                  # LLM integration
│   │   ├── inference.py        # Model loading and selection
│   │   ├── llama_cpp_loader.py # Llama.cpp integration
│   │   ├── llm_interface.py    # LLM abstraction
│   │   ├── local_models.py     # Local model implementations
│   │   └── openrouter.py       # OpenRouter API integration
│   ├── tools/                   # Tool implementations
│   │   ├── code_editor.py      # Code editing tools
│   │   ├── code_tools.py       # Code analysis tools
│   │   ├── filesystem.py       # File operations
│   │   ├── shell.py            # Command execution
│   │   └── system_info.py      # System information
│   └── ui/                      # User interface
│       ├── cli.py              # Main CLI entry point
│       ├── cli_handlers/       # Modular CLI handlers
│       │   ├── code_handlers.py
│       │   ├── commands.py
│       │   ├── translation_helpers.py
│       │   └── basic_interactive.py
│       ├── display.py          # Output formatting
│       └── interactive/        # Interactive mode
│           ├── interactive_mode.py
│           ├── modes.py        # Mode handlers (agent/ask/plan)
│           ├── commands.py     # Slash commands
│           ├── keybindings.py  # Keyboard shortcuts
│           ├── prompt.py       # Prompt display
│           ├── completers.py   # Auto-completion
│           └── utils.py        # Utilities
├── config/                      # Configuration files
│   ├── models.yaml
│   └── plugins.yaml
├── tests/                       # Test suite
├── requirements.txt             # Core dependencies
├── requirements-llm.txt         # LLM dependencies (optional)
└── pyproject.toml              # Project configuration
```

## 🔌 Model Support

### Local Models

Joshu supports various local models via `llama-cpp-python`:

- **Llama 3** (8B, 70B)
- **Mistral** (7B, Mixtral 8x7B)
- **CodeLlama** (7B, 34B)
- **Gemma** (2B, 9B)

Configure via environment variables:

```bash
LLAMA_CPP_MODEL_LLAMA3_8B=/path/to/model.gguf
LLAMA_CPP_MODEL_MISTRAL_7B=/path/to/model.gguf
```

### Cloud Models (via OpenRouter)

When API keys are configured, Joshu automatically uses cloud models for better performance:

- OpenAI models (GPT-4o, GPT-4o-mini, etc.)
- Anthropic Claude
- Google Gemini
- DeepSeek
- And many more via OpenRouter

## 🛡️ Security

### Safety Features

- **Command Validation**: Multi-level safety checks before execution
- **Danger Detection**: Identifies destructive commands (rm, format, etc.)
- **User Confirmation**: Prompts for confirmation on risky operations
- **Sandbox Mode**: Optional sandbox environment for testing
- **Input Validation**: Comprehensive prompt injection protection
- **Audit Logging**: Complete operation history for review

### Safety Levels

Commands are assessed with three safety levels:

- **SAFE**: Can be executed automatically (if `auto_execute=true`)
- **WARNING**: Requires user confirmation
- **DANGER**: Blocked by default, requires explicit override

Example safety check:

```bash
joshu "delete all files in /home"
→ ⚠️  DANGER: This command could delete important files
→ Command blocked for safety.
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/Faycacalraghibi/joshu-assistant.git
cd joshu-assistant

# Create development environment
python -m venv dev-env
source dev-env/bin/activate  # On Windows: dev-env\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .

# Run tests
pytest tests/

# Run linting
flake8 src/
black src/
```

### Areas for Contribution

- Model optimization and quantization
- New plugin development
- UI/UX improvements
- Documentation and tutorials
- Performance benchmarking
- Security enhancements
- Additional tool integrations

## 📊 Performance

Performance varies based on model and hardware:

| Model | Response Time | Memory Usage | Quality |
|-------|--------------|--------------|---------|
| Llama-3-8B (local) | ~2s | 8GB RAM | 8.2/10 |
| Llama-3-70B (local) | ~8s | 40GB RAM | 9.1/10 |
| GPT-4o-mini (cloud) | ~1s | 0GB (API) | 9.0/10 |
| GPT-4o (cloud) | ~2s | 0GB (API) | 9.5/10 |

*Benchmarks on NVIDIA A100 40GB for local models*

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by Anthropic's Claude CLI
- Built with amazing open-source models:
  - [Llama 3](https://llama.meta.com/) by Meta
  - [Mistral](https://mistral.ai/) by Mistral AI
  - [Code Llama](https://github.com/facebookresearch/codellama) by Meta
  - [OpenRouter](https://openrouter.ai/) for cloud model access

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Faycacalraghibi/joshu-assistant/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Faycacalraghibi/joshu-assistant/discussions)

---

Made with ❤️ by the Joshu community

**Democratizing AI assistance, one command at a time.**
