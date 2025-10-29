# Fixing Joshu Configuration

The error you encountered is due to using a model (`deepseek/deepseek-chat-v3.1:free`) that is not available or properly configured with OpenRouter.

## Solution

Run the provided fix script to update your configuration:

```bash
python fix_joshu.py
```

This will update your model configuration from `deepseek/deepseek-chat-v3.1:free` to `openai/gpt-4o-mini`, which is a reliable free model that works with OpenRouter.

## Manual Fix

Alternatively, you can manually edit your configuration file at `~/.joshu/config.yaml` and change the model line from:

```yaml
model: deepseek/deepseek-chat-v3.1:free
```

to:

```yaml
model: openai/gpt-4o-mini
```

## Why This Change?

The `openai/gpt-4o-mini` model is:
- Free to use
- Widely available on OpenRouter
- Reliable for command translation tasks
- Well-tested with Joshu

After making this change, restart your OpenCLI session and the 404 error should be resolved.