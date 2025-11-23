# Joshu

> AI-powered command-line assistant that speaks your language

![Joshu Architecture](diagram.png)

## What is Joshu?

Joshu transforms natural language into shell commands, code, and autonomous task execution. Three modes. One assistant. Zero complexity.

## Quick Start

```bash
# Install
git clone https://github.com/Faycacalraghibi/joshu-assistant.git
cd joshu-assistant
pip install -e .

# Run
joshu interactive
```

## Three Modes

**🤖 Agent** — Autonomous execution  
**💬 Ask** — Q&A without commands  
**📋 Plan** — Step-by-step breakdown

Switch modes: `/agent`, `/ask`, `/plan`

## Core Features

- Natural language → Shell commands
- Code generation & editing
- Session management
- Semantic memory (ChromaDB)
- Multi-model support (local & cloud)
- Safety-first validation

## Commands

```bash
# Interactive mode
joshu interactive

# One-shot command
joshu "list all Python files modified today"

# Code generation
joshu code "write a REST API with Flask"

# Configuration
joshu config --list
```

## Interactive Commands

### Sessions
```
/session         # Current session
/session list    # All sessions
/session new     # New session
```

### Memory
```
/memory search <query>  # Semantic search
/memory status          # Statistics
/memory clear           # Clear all
```

### Modes
```
/agent    # Autonomous mode
/ask      # Q&A mode
/plan     # Planning mode
```

## Configuration

Create `~/.joshu/config.yaml`:

```yaml
model: "llama-3-8b"
safety_mode: true
max_tokens: 4096
semantic_memory_enabled: true
semantic_memory_similarity_threshold: 0.3
```

Or use environment variables:

```bash
export OPENROUTER_API_KEY=your_key
export JOSHU_MODEL=llama-3-8b
```

## Models

**Local:** Llama 3, Mistral, CodeLlama, Gemma  
**Cloud:** GPT-4o, Claude, Gemini (via OpenRouter)

## Safety

- Multi-level command validation
- Destructive command detection
- User confirmation prompts
- Sandbox mode
- Audit logging

## Architecture

See [diagram.png](diagram.png) for full architecture overview.

**Core Components:**
- `src/joshu/core/` — Assistant logic & context
- `src/joshu/models/` — LLM integration
- `src/joshu/ui/` — CLI & interactive mode
- `src/joshu/tools/` — Code, filesystem, shell

## Installation Options

**Basic (core features):**
```bash
pip install -e .
```

**With semantic memory:**
```bash
pip install -e .[semantic]
```

**With local LLM support:**
```bash
pip install -e .[llm]
```

**Full install:**
```bash
pip install -e .[dev,llm,semantic]
```

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -e .[dev]

# Test
pytest tests/

# Format
black src/
```

## Documentation

Detailed documentation in [`docs/`](docs/):
- [Enhanced Interactive Mode](docs/enhanced_interactive_mode.md)
- [VLLM Server Integration](docs/VLLM_SERVER_INTEGRATION.md)
- [Rules & Guidelines](docs/Rules.md)

## License

MIT License - See [LICENSE](LICENSE)

---

**Democratizing AI assistance, one command at a time.**
