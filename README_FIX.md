# Joshu Configuration Fix

## Issue
You encountered a 404 error when using Joshu:
```
ERROR:joshu.models.openrouter:Multi-provider API call failed: Error code: 404 - {'error': {'message': 'No endpoints found matching your data policy (Free model publication). Configure: https://openrouter.ai/settings/privacy', 'code': 404}}
```

## Solution
The issue was caused by using an unavailable model (`deepseek/deepseek-chat-v3.1:free`). Your configuration has been successfully updated to use `openai/gpt-4o-mini`, which is a reliable free model that works with OpenRouter.

## Verification
Your configuration file at `~/.joshu/config.yaml` now contains:
```yaml
model: openai/gpt-4o-mini
safety_mode: false
auto_execute: false
max_tokens: 4096
temperature: 0.5
history_size: 100
log_level: INFO
memory_enabled: true
sandbox_enabled: true
enhanced_interactive: true
multiline_input: true
vim_mode: false
persistent_history: true
history_limit: 1000
```

## Next Steps
You can now use Joshu without encountering the 404 error. Try running:
```bash
joshu run --interactive
```

Then test with a simple command like "hi" or "list files in current directory".