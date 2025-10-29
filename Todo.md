# 🎯 MVP Core Features for OpenCLI Assistant

## 1. **Natural Language Command Translation** [Priority: CRITICAL] ✅ COMPLETED

```bash
# Core functionality - the heart of the CLI assistant
joshu "list all python files modified today"
→ find . -name "*.py" -mtime -1

joshu "show disk usage of current directory"
→ du -sh .

joshu "find large files over 100MB"
→ find . -type f -size +100M -exec ls -lh {} \;
```

**Technical Requirements:**

- Pattern matching for common command types
- Safety validation before execution
- Command explanation before running
- History tracking of translations[^1][^2]

## 2. **Interactive Chat Mode** [Priority: CRITICAL] ✅ COMPLETED

```bash
joshu --interactive
> You: How do I compress this folder?
> Assistant: I can help you compress the folder. Here are your options:
> 1. tar -czf folder.tar.gz foldername  (gzip compression)
> 2. zip -r folder.zip foldername       (zip format)
> 
> Which format would you prefer? [1/2]
```

**Features:**

- Persistent conversation context
- Multi-turn dialogue support
- Command suggestion and confirmation
- Exit/help commands[^3][^4]

## 3. **Local LLM Integration** [Priority: CRITICAL] ✅ COMPLETED

```python
# Core model management
- Model loading/unloading ✅
- Memory-efficient inference ✅
- Response streaming ✅
- Model switching (llama-3-8b, mistral-7b, etc.) ✅
```

**Technical Stack:**

- `llama-cpp-python` for local inference
- `transformers` for model management
- Automatic model downloading and caching
- GPU/CPU optimization based on hardware[^5]

## 4. **Command Safety \& Validation** [Priority: HIGH] ✅ COMPLETED

```bash
# Safety features
joshu "delete all files in /home"
→ ⚠️  DANGER: This command could delete important files
→ Command blocked for safety. Did you mean to delete files in current directory?
→ Suggested safer alternative: rm -i *.tmp
```

**Safety Features:**

- Destructive command detection
- User confirmation for risky operations
- Sandbox mode for testing
- Command explanation and alternatives[^6]

## 5. **Basic File Operations** [Priority: HIGH] ✅ COMPLETED

```bash
# File system intelligence
joshu "show me the structure of this project"
joshu "find configuration files"
joshu "what's in the log directory?"
joshu "backup my source code"
```

**Capabilities:**

- Directory traversal and analysis
- File content preview
- Permission checking
- Basic file manipulation[^7][^3]

## 6. **Configuration Management** [Priority: MEDIUM]

```yaml
# ~/.joshu/config.yaml
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

**Features:**

- User preferences storage
- Model selection
- Safety level configuration
- Output formatting options

## 7. **Command History \& Learning** [Priority: MEDIUM] ✅ COMPLETED

```bash
# History and context
joshu --history
joshu --repeat-last
joshu --explain-last

# Context awareness
> Previously you helped me with git commands
> Now I need to deploy this app
```

**Features:**

- Command execution history
- Pattern learning from user behavior
- Contextual suggestions
- Favorite commands[^2][^1]

## 8. **Help \& Documentation** [Priority: MEDIUM] ✅ COMPLETED

```bash
joshu --help
joshu --examples
joshu --commands [category]
joshu --explain "tar command"
```

**Features:**

- Built-in help system
- Command examples
- Tutorial mode
- Troubleshooting guides

***

# 🧠 TODO.md — Advanced Claude-like CLI Integration Roadmap

> **Reference Docs**  
>
> - [CLI Reference](https://docs.claude.com/en/docs/claude-code/cli-reference)  
> - [Interactive Mode](https://docs.claude.com/en/docs/claude-code/interactive-mode)  
> - [Slash Commands](https://docs.claude.com/en/docs/claude-code/slash-commands)  
> - [Checkpointing](https://docs.claude.com/en/docs/claude-code/checkpointing)  
> - [Hooks](https://docs.claude.com/en/docs/claude-code/hooks)

---

## ✅ Core Features (Already Implemented)

- [x] Natural Language → CLI Command Translation  
- [x] Interactive Chat Mode  
- [x] Local Model Context Switching  
- [x] Command Validation & Safety Layer  
- [x] File System Operations (list, read, edit, permissions)  
- [x] Contextual History & Auto-suggestions  
- [x] Built-in Help and Docs lookup  

---

## 🚀 New Advanced Feature Targets

### 1. CLI/SDK Parity

*(Ref: [CLI Reference](https://docs.claude.com/en/docs/claude-code/cli-reference))*

- Implement all `joshu` flags and command options:
  - `-p`, `--resume`, `--add-dir`, `--agents`, `--output-format`, `--verbose`, etc.
- Add update/version management and session persistence.
- Introduce flexible input/output formats (text, JSON, streaming).
- Enable contextual model switching: `--model <name>`.
- Support directory scoping and multi-path inclusion.
- Integrate fine-grained tool permission modes (`--allowedTools`, `--disallowedTools`).

---

### 2. Enhanced Interactive Mode

*(Ref: [Interactive Mode](https://docs.claude.com/en/docs/claude-code/interactive-mode))*

- Support multiline input, reverse search, and navigation (`Ctrl+R`, `Ctrl+J`, etc.).
- Add keyboard shortcuts for:
  - Exit / Clear / Verbose toggle / Bash background (`Ctrl+B`).
- Implement Vim-style **NORMAL/INSERT** modes for power users.
- Per-directory persistent command history with `/clear` and `/history`.
- Add direct bash integration with `!` and file injection with `@file`.

---

### 3. Slash Commands

*(Ref: [Slash Commands](https://docs.claude.com/en/docs/claude-code/slash-commands))*

- Core commands to support:
  `/add-dir`, `/agents`, `/clear`, `/config`, `/doctor`, `/model`, `/permissions`, `/review`, `/rewind`, `/usage`, `/vim`
- Namespaced slash command system (`/plugin:cmd`).
- Autodiscovery of project or user-defined slash commands.
- Support for arguments, environment substitution, and file injection (`$1`, `@filename`).
- Integrate permission control, per-command model selection, and disable logic.

---

### 4. Checkpointing & Undo System

*(Ref: [Checkpointing](https://docs.claude.com/en/docs/claude-code/checkpointing))*

- Create automatic checkpoints after each edit or command execution.  
- Implement `/rewind` or `Esc Esc` shortcuts for state restoration.  
- Multi-level checkpoint depth (configurable).  
- Handle non-checkpointable actions (e.g., shell commands) gracefully.  
- Persistent checkpoint tracking per session ID.

---

### 5. Hooks Framework

*(Ref: [Hooks](https://docs.claude.com/en/docs/claude-code/hooks))*

- Add event-driven hook system:
  - `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`, `PreCompact`, etc.
- Allow hook registration at user, project, or plugin levels.
- Implement both **blocking** (modify context) and **non-blocking** (observe) hooks.
- Secure sandboxing for all shell or script hooks.
- Include a debug/log mode for hook tracing.

---

### 6. Agents & Subagents

- Allow agent definitions with independent:
  - Prompts, models, and tool sets.
- Enable subagent invocation for task delegation (e.g., reviewing, debugging).
- Context switching between agents mid-session.

---

### 7. Plugin & Skills Ecosystem

- Introduce a lightweight plugin API for third-party skill injection.
- Namespace and register custom slash commands + hooks from plugins.
- Implement `/plugin install`, `/plugin list`, `/plugin remove`.

---

### 8. Security, Permissions & Policy Layer

- Sandbox all external or destructive commands.
- Request confirmation for critical operations.
- Audit and log all system-level actions with contextual metadata.
- Implement `--permission-mode` levels (strict, relaxed, manual).

---

## 🧩 Development Checklist

- [ ] Implement CLI flags and options (parity with Claude Code CLI).  
- [ ] Integrate interactive REPL shortcuts (cross-terminal testing).  
- [ ] Add slash command parser and runtime registry.  
- [ ] Develop checkpoint manager with serialization and restore logic.  
- [ ] Design secure event-based hook system.  
- [ ] Introduce subagent orchestration layer.  
- [ ] Prototype plugin system and skill discovery mechanism.  
- [ ] Write internal docs with official references.  

---

## 📚 Always Refer

When in doubt, consult:

- [CLI Reference](https://docs.claude.com/en/docs/claude-code/cli-reference)  
- [Interactive Mode](https://docs.claude.com/en/docs/claude-code/interactive-mode)  
- [Slash Commands](https://docs.claude.com/en/docs/claude-code/slash-commands)  
- [Checkpointing](https://docs.claude.com/en/docs/claude-code/checkpointing)  
- [Hooks](https://docs.claude.com/en/docs/claude-code/hooks)

---

### 🧭 Notes

This document serves as the **living specification** for building Claude-like CLI parity within your assistant.  
Update it as new subfeatures roll out or existing ones reach completion.



## 🚧 MVP Feature Boundaries (What to EXCLUDE Initially)

### Not in MVP v1

- ❌ GUI automation/computer use
- ❌ RAG with external documentation
- ❌ Plugin system
- ❌ Cloud model integration
- ❌ Multi-language support
- ❌ Advanced personalization
- ❌ Code execution environments
- ❌ Integration with external APIs

***

## 📋 MVP Development Phases

### **Phase 1: Foundation** (Week 1-2)

- Basic CLI interface with `typer`
- Simple model loading with `llama-cpp-python`
- Basic natural language to command translation
- Essential safety validation

### **Phase 2: Core Functionality** (Week 3-4)

- Interactive chat mode
- Command history
- Configuration management
- File system operations

### **Phase 3: Polish \& Safety** (Week 5-6)

- Enhanced safety features
- Better error handling
- Documentation and help system
- Basic testing suite

***

## 🎯 Success Metrics for MVP

1. **Core Functionality**: Can translate 80% of common CLI tasks
2. **Safety**: Zero destructive commands executed without confirmation
3. **Performance**: <3 second response time for simple queries
4. **Usability**: New users can perform basic tasks within 5 minutes
5. **Reliability**: 95% uptime during interactive sessions

***

## 💡 MVP User Stories

```gherkin
Feature: Natural Language Command Translation
  Scenario: User wants to find files
    Given I am in a project directory
    When I ask "find all Python files"
    Then the system suggests "find . -name '*.py'"
    And asks for confirmation before executing

Feature: Interactive Help
  Scenario: User needs guidance
    Given I am new to Linux commands
    When I ask "how do I copy files?"
    Then the system explains cp command with examples
    And offers to help with specific file copying task
```

This MVP focuses on the core value proposition - making the command line more accessible through natural language - while keeping the scope manageable and ensuring a solid foundation for future features.[^8][^1][^2][^6]
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^9]</span>

<div align="center">⁂</div>

[^1]: <https://arxiv.org/pdf/2309.06551.pdf>

[^2]: <http://arxiv.org/pdf/2002.00762.pdf>

[^3]: <https://www.aclweb.org/anthology/D18-2025.pdf>

[^4]: <https://www.mdpi.com/2504-3900/54/1/30/pdf>

[^5]: <https://arxiv.org/pdf/2306.08640.pdf>

[^6]: <https://arxiv.org/pdf/2409.02711.pdf>

[^7]: <https://www.ijfmr.com/papers/2024/6/30587.pdf>

[^8]: <https://ieeexplore.ieee.org/document/10628598/>

[^9]: <https://ieeexplore.ieee.org/document/11171116/>

[^10]: <https://arxiv.org/html/2404.02475v1>

[^11]: <https://arxiv.org/html/2409.13588v2>

[^12]: <https://arxiv.org/pdf/2403.08299.pdf>

[^13]: <https://arxiv.org/pdf/2309.11436.pdf>

[^14]: <https://arxiv.org/pdf/2403.14592.pdf>

[^15]: <https://arxiv.org/pdf/2410.21784.pdf>

[^16]: <https://arxiv.org/pdf/2401.11314.pdf>

[^17]: <https://aclanthology.org/2023.emnlp-demo.20.pdf>

[^18]: <https://aclanthology.org/2022.emnlp-main.449.pdf>

[^19]: <http://arxiv.org/pdf/2304.11938v1.pdf>

[^20]: <http://arxiv.org/pdf/2403.04327.pdf>
