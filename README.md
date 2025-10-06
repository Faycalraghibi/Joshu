# OpenCLI

**OpenCLI** is a terminal-based AI assistant that leverages the [OpenRouter API](https://openrouter.ai/) to provide seamless access to multiple open-source and commercial LLMs. Designed for developers, it offers intelligent code suggestions, multi-turn conversations, and more—directly from your command line.

---

## Features

- **Unified API Access**: Connect to over 400 AI models from providers like OpenAI, Anthropic, Google, Meta, and more using a single API key.
- **Model Routing & Fallback**: Automatically switch between models based on availability and cost-effectiveness.
- **Conversation History**: Maintain multi-turn context with options to save and load chat history.
- **Code Assistance**: Get code completions, refactorings, and documentation generation.
- **Git Integration**: Interact with your codebase using GitPython for version control operations.
- **Windows Compatibility**: Fully compatible with PowerShell and CMD.

---

## Requirements

- Python 3.10+
- Libraries:
  - `openai` (or OpenRouter API client)
  - `python-dotenv`
  - `click`
  - `requests`
  - `GitPython`
  - `pylint`
  - `pytest`

---

## Installation

1. Clone the repository:

```powershell
git clone https://github.com/Faycalraghibi/OpenCLI.git
cd OpenCLI
