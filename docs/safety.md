# Safety Features

## Overview

Joshu includes comprehensive command safety validation to prevent dangerous operations. Before executing commands (especially destructive ones), Joshu analyzes them for potential risks and provides warnings, alternatives, or blocks execution entirely.

## Safety Assessment

Every command is analyzed for:

- **Destructive Operations**: File deletion, formatting, etc.
- **Privilege Escalation**: sudo, administrator access
- **System-Critical Paths**: /, system32, etc.
- **Dangerous Patterns**: Recursive deletion, wildcards in rm
- **Platform-Specific Risks**: Windows vs Unix differences

## Danger Levels

Safety reports include a danger level:

- **LOW**: Safe command, no warnings
- **MEDIUM**: Potentially risky (e.g., file deletion, sudo)
- **HIGH**: Very dangerous (e.g., deleting system directories)
- **CRITICAL**: Catastrophic risk (e.g., `rm -rf /`)

## Usage

### Automatic Safety Checks

Safety checks happen automatically:

```bash
# Safe command - executes normally
$ joshu "show disk usage"
✓ Safe command
Executing: df -h

# Dangerous command - shows warning
$ joshu "delete all temp files"
⚠️  WARNING: Destructive operation detected
Command: rm -rf /tmp/*
Danger Level: HIGH
Reasons:
  - Destructive operation: may delete files permanently
  - Uses wildcard (*) which could match unintended files

Suggested alternative: Delete specific files only: rm /tmp/specific_file

Execute anyway? [y/N]:
```

### Sandbox Mode

Sandbox mode blocks ALL destructive commands:

**~/.joshu/config.yaml**:
```yaml
sandbox_enabled: true
```

With sandbox enabled:

```bash
$ joshu "remove file.txt"
❌ BLOCKED: Sandbox mode enabled
Command: rm file.txt
Danger Level: CRITICAL
Reasons:
  - Sandbox mode: All destructive commands are blocked

Suggested alternative: Review file first: cat file.txt
```

## Programmatic Usage

### Safety Assessment

```python
from joshu.core.safety import assess_command_safety

# Assess a command
report = assess_command_safety("rm -rf /home/user/temp")

print(f"Safe: {report.safe}")
print(f"Danger Level: {report.danger_level}")
print(f"Reasons: {report.reasons}")
print(f"Alternative: {report.suggested_alternative}")
```

### Response Structure

```python
class SafetyReport:
    safe: bool                      # Is command safe?
    danger_level: str               # LOW, MEDIUM, HIGH, CRITICAL
    reasons: List[str]              # Why it's unsafe
    suggested_alternative: Optional[str]  # Safer alternative
```

### Examples

#### Safe Command

```python
report = assess_command_safety("ls -la")

# SafetyReport(
#     safe=True,
#     danger_level="LOW",
#     reasons=[],
#     suggested_alternative=None
# )
```

#### Destructive Command

```python
report = assess_command_safety("rm file.txt")

# SafetyReport(
#     safe=False,
#     danger_level="MEDIUM",
#     reasons=["Destructive operation: may delete files"],
#     suggested_alternative="Move to trash: mv file.txt ~/.trash/"
# )
```

#### Critical Command

```python
report = assess_command_safety("rm -rf /")

# SafetyReport(
#     safe=False,
#     danger_level="CRITICAL",
#     reasons=["DANGER: This command will delete your entire system"],
#     suggested_alternative="Delete files interactively: rm -i"
# )
```

## Platform-Specific Detection

Safety rules adapt to your operating system:

### Unix/Linux

```python
# Detects Unix-specific dangers
assess_command_safety("sudo rm -rf /")  # CRITICAL
assess_command_safety("rm -rf /home")    # HIGH
assess_command_safety("chmod 777 /")     # HIGH
```

### Windows

```python
# Detects Windows-specific dangers
assess_command_safety("del /s /q C:\\")  # CRITICAL
assess_command_safety("format C:")       # CRITICAL
assess_command_safety("rd /s /q C:\\")   # CRITICAL
```

## Dangerous Patterns

### Root/Drive Deletion

**Unix**:
```bash
rm -rf /              # CRITICAL
rm -rf /*             # CRITICAL
rm -r /home           # HIGH
```

**Windows**:
```bash
del /s /q C:\         # CRITICAL
format C:             # CRITICAL
rd /s /q C:\Windows   # HIGH
```

### Sudo/Elevation

```bash
sudo rm file.txt      # MEDIUM (privilege escalation)
sudo apt remove pkg   # MEDIUM
```

Sudo on Windows is not flagged (not a recognized pattern).

### Wildcards in Destructive Commands

```bash
rm -rf *              # HIGH (wildcard deletion)
del /s /q *.*         # HIGH
```

### System Directory Access

**Unix**:
```bash
rm -rf /etc           # HIGH
rm -rf /usr/bin       # HIGH
rm -rf /var           # HIGH
```

**Windows**:
```bash
del /s C:\Windows     # HIGH
del /s C:\Program Files # HIGH
```

## Configuration

### Enable/Disable Safety

```yaml
# ~/.joshu/config.yaml
safety_mode: true      # Enable safety checks
sandbox_enabled: false # Disable sandbox mode
```

### Safety in Auto-Fix

Auto-fix respects safety settings:

```python
from joshu.core.auto_fix import analyze_error_and_generate_fix
from joshu.core.safety import assess_command_safety

# Generate fix
fix = analyze_error_and_generate_fix(...)

if fix:
    # Safety check before execution
    safety = assess_command_safety(fix.command,
                                   sandbox_mode=config.get("sandbox_enabled"))

    if not safety.safe:
        print(f"Unsafe fix rejected: {safety.reasons}")
        fix = None
```

## Suggested Alternatives

Safety reports often include safer alternatives:

| Dangerous Command | Suggested Alternative |
|-------------------|----------------------|
| `rm -rf /` | Delete files interactively: `rm -i` |
| `del /s /q C:\` | Delete specific files only: `del *.tmp` |
| `chmod 777 /` | Set specific directory permissions |
| `sudo rm file` | Check file permissions first |

## Best Practices

1. **Keep Safety  Enabled**: Don't disable safety checks in production
2. **Use Sandbox for Testing**: Test commands in sandbox mode first
3. **Review Warnings**: Always read safety warnings before proceeding
4. **Check Alternatives**: Consider suggested safer alternatives
5. **Be Cautious with Wildcards**: Especially in deletion commands

## Advanced Usage

### Custom Safety Rules

Extend safety checking for domain-specific rules:

```python
from joshu.core.safety import assess_command_safety, SafetyReport

def assess_with_custom_rules(command: str) -> SafetyReport:
    # Standard safety check
    report = assess_command_safety(command)

    # Add custom rules
    if "production" in command and "delete" in command:
        report.safe = False
        report.danger_level = "CRITICAL"
        report.reasons.append("Production deletion blocked")

    return report
```

### Allowlists

For automation, you might allowlist specific patterns:

```python
SAFE_PATTERNS = [
    r"^ls\b",
    r"^pwd\b",
    r"^echo\b"
]

import re

def is_allowlisted(command: str) -> bool:
    return any(re.match(pattern, command) for pattern in SAFE_PATTERNS)

if is_allowlisted("ls -la"):
    # Skip safety check
    execute(command)
```

## Limitations

### What Safety Detects

✅ Common destructive commands
✅ System-critical path access
✅ Privilege escalation
✅ Dangerous flag combinations
✅ Wildcard risks

### What Safety Doesn't Detect

❌ Application-specific dangerous operations
❌ Commands that modify data through APIs
❌ Complex shell scripts (only checks top-level command)
❌ Malicious code in script files
❌ Resource exhaustion (fork bombs, etc.)

## Troubleshooting

### False Positives

Sometimes safe commands are flagged:

```bash
# Flagged as dangerous (rm command)
$ rm ~/old_backups/temp.txt

# Override: Use full path
$ rm /home/user/old_backups/temp.txt
```

### Bypassing Safety (Not Recommended)

For scripts/automation only:

```python
# Disable safety for specific command
from joshu.tools.shell import run_command

# WARNING: Skips ALL safety checks
exit_code, stdout, stderr = run_command("rm file.txt")
```

**Never bypass safety for user-input commands!**

## Related Documentation

- [Auto-Fix](auto-fix.md) - Auto-fix uses safety validation
- [Configuration](configuration.md) - Safety configuration options
- [Testing Guide](testing-guide.md) - Testing safety features
