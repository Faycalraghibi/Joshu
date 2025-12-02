# Auto-Fix

## Overview

Auto-Fix automatically attempts to fix failed commands by analyzing errors and generating corrections. When a command fails, Joshu uses an LLM to understand the error and suggest a fix, then executes the corrected command after safety validation.

## How It Works

1. **Command Fails**: Initial command returns non-zero exit code
2. **Error Analysis**: LLM analyzes command, error output, and exit code
3. **Fix Generation**: LLM suggests corrected command with explanation
4. **Safety Check**: Proposed fix is validated for safety
5. **Execution**: If safe, corrected command is executed
6. **Retry Limit**: Process repeats up to `auto_fix_max_attempts` times

## Configuration

### Enable Auto-Fix

Auto-fix is disabled by default. Enable it in your config:

**~/.joshu/config.yaml**:
```yaml
auto_fix_enabled: true
auto_fix_max_attempts: 2
```

**Or via environment**:
```bash
export JOSHU_AUTO_FIX_ENABLED=true
export JOSHU_AUTO_FIX_MAX_ATTEMPTS=2
```

### Configuration Options

- `auto_fix_enabled` (bool): Enable/disable auto-fix
- `auto_fix_max_attempts` (int): Maximum retry attempts (default: 2)
- Safety settings also apply (sandbox mode blocks unsafe fixes)

## Usage Examples

### Typo Correction

```bash
$ joshu "sl -la"
Error: command not found: sl

Auto-fix: Detected typo
Fixed command: ls -la
Confidence: 95%

Execute fixed command? [y/N]: y
# Files listed successfully
```

### Wrong Flag

```bash
$ joshu "grep --regex 'pattern' file.txt"
Error: unrecognized option '--regex'

Auto-fix: Corrected flag
Fixed command: grep -E 'pattern' file.txt
Confidence: 90%

Execute? [y/N]: y
# Pattern matches shown
```

### Missing Dependency

```bash
$ joshu "run python script.py"
Error: python: command not found

Auto-fix: Added python3
Fixed command: python3 script.py
Confidence: 85%

Execute? [y/N]: y
# Script runs
```

## How Fixes Are Generated

### Error Analysis

The LLM receives:
- Original command
- Error message/output
- Exit code
- System context (OS, shell)
- Conversation history

### Fix Response Format

The LLM returns JSON:

```json
{
  "command": "ls -la",
  "explanation": "Fixed typo: 'sl' → 'ls'",
  "confidence": 0.95
}
```

### Confidence Scoring

Confidence is automatically calculated based on:
- Explanation quality (length and detail)
- Command similarity to original
- Error type recognition

Confidence ranges:
- **0.8-1.0**: High confidence (minor typo, clear fix)
- **0.5-0.8**: Medium confidence (flag correction, path fix)
- **0.0-0.5**: Low confidence (complex error, uncertain fix)

## Safety Integration

All auto-fix suggestions go through safety validation:

```python
from joshu.core.auto_fix import analyze_error_and_generate_fix
from joshu.core.safety import assess_command_safety

# Generate fix
fix = analyze_error_and_generate_fix(
    original_command="rm file.txt",
    error_output="permission denied",
    exit_code=1
)

if fix:
    # Safety check proposed fix
    safety_report = assess_command_safety(fix.command)

    if not safety_report.safe:
        print(f"Unsafe fix rejected: {safety_report.reasons}")
        fix = None
```

### Rejected Fixes

Unsafe fixes are automatically rejected:

```bash
$ joshu "delete temp file"
Error: permission denied

Auto-fix: Use sudo
Proposed: sudo rm temp_file
❌ Rejected: Elevates privileges (unsafe)

Suggested alternative: Check file permissions first
```

## Programmatic Usage

### Check If Auto-Fix Should Run

```python
from joshu.core.auto_fix import should_attempt_auto_fix

config = {
    "auto_fix_enabled": True,
    "auto_fix_max_attempts": 2
}

# First attempt
if should_attempt_auto_fix(config, attempt=0):
    # Try auto-fix
    pass

# After max attempts
if not should_attempt_auto_fix(config, attempt=2):
    print("Max attempts reached")
```

### Generate Fix

```python
from joshu.core.auto_fix import analyze_error_and_generate_fix
from joshu.core.context_provider import ContextProvider

context = ContextProvider()

fix = analyze_error_and_generate_fix(
    original_command="sl -la",
    error_output="command not found: sl",
    exit_code=127,
    context_provider=context  # Optional: provides history
)

if fix:
    print(f"Fix: {fix.command}")
    print(f"Explanation: {fix.explanation}")
    print(f"Confidence: {fix.confidence:.0%}")
```

### Execute With Auto-Fix

```python
from joshu.tools.shell import run_command_with_auto_fix

config = {
    "auto_fix_enabled": True,
    "auto_fix_max_attempts": 2,
    "sandbox_enabled": False
}

exit_code, stdout, stderr, fixed_cmd = run_command_with_auto_fix(
    "sl -la",
    config,
    attempt=0
)

if fixed_cmd:
    print(f"Command was fixed to: {fixed_cmd}")
```

## Limitations

### What Auto-Fix Can Handle

✅ Typos in command names
✅ Incorrect flags/options
✅ Missing quotes or escapes
✅ Wrong paths (if inferable)
✅ Simple syntax errors

### What Auto-Fix Cannot Handle

❌ Missing dependencies (just suggests install)
❌ Complex logic errors in scripts
❌ Permission issues (won't sudo without user confirmation)
❌ Network connectivity problems
❌ Invalid credentials

### Retry Limit

Auto-fix will stop after `auto_fix_max_attempts`:

```python
# Attempt 0: Try fix #1
# Attempt 1: Try fix #2
# Attempt 2: Give up (max reached)
```

This prevents infinite loops when fixes don't work.

## Best Practices

1. **Start Conservative**: Begin with `auto_fix_max_attempts: 1`
2. **Review Fixes**: Don't blindly accept all fixes
3. **Enable Safety**: Keep `sandbox_enabled: true` in production
4. **Provide Context**: More conversation history = better fixes
5. **Monitor Confidence**: Be cautious with low-confidence fixes

## Troubleshooting

### Auto-Fix Not Triggering

- Verify `auto_fix_enabled: true` in config
- Check command actually failed (exit code != 0)
- Ensure not already at max attempts

### Poor Fix Quality

- LLM may need more context - add conversation history
- Try different model (some are better at error analysis)
- Increase verbosity to see LLM reasoning

### Fixes Keep Failing

- May have hit max attempts
- Original problem may not be fixable with simple command change
- Check if dependency needs to be installed first

## Related Documentation

- [Safety Features](safety.md) - Command safety validation
- [Models & Providers](models-and-providers.md) - Configure LLM for fixes
- [Configuration](configuration.md) - Auto-fix settings
