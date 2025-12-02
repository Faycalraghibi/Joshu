# Web Fetch Tool

## Overview

The `web_fetch` tool enables Joshu to fetch and process content from web URLs. When you ask Joshu to read a webpage, analyze a URL, or extract information from a website, this tool retrieves the actual content and converts it to readable text.

## Quick Start

```bash
# In interactive mode
joshu --interactive

# Ask about a URL
> Summarize the content at https://example.com/article
```

The agent will:
1. Prompt for your approval (security measure)
2. Fetch the page content
3. Convert HTML to readable text
4. Provide a response based on the content

## Configuration

Add to `config/config.yaml`:

```yaml
# Web Fetch Settings
web_fetch_enabled: true          # Enable/disable web fetch
web_fetch_timeout: 15            # Request timeout in seconds
web_fetch_max_content_length: 50000  # Max characters to return
```

## Security

The `web_fetch` tool requires **user approval** before accessing any URL. This security measure:
- Prevents unauthorized external requests
- Gives you control over what URLs are accessed
- Matches Gemini CLI's security model

## Use Cases

| Use Case | Example Prompt |
|----------|---------------|
| Summarize article | "Summarize https://example.com/article" |
| Extract information | "What are the main features listed at https://docs.python.org/3/whatsnew/3.12.html" |
| Compare pages | "Compare the content of these two URLs..." |
| Read documentation | "Explain the API described at https://api.example.com/docs" |

## API Reference

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | ✅ | HTTP/HTTPS URL to fetch |
| `instruction` | string | ❌ | Optional processing instruction |

### Response

```python
{
    "success": True,
    "url": "https://example.com",
    "source": "https://example.com",
    "content": "# Page Title\n\nPage content...",
    "instruction": "summarize",  # if provided
    "truncated": False,
    "error": None
}
```

## Troubleshooting

### URL Not Fetching

1. Check `web_fetch_enabled: true` in config
2. Ensure URL is valid HTTP/HTTPS
3. Increase `web_fetch_timeout` for slow sites

### Content Truncated

Large pages are truncated at `web_fetch_max_content_length` (default: 50,000 chars). Increase this value if needed.

## See Also

- [Web Search Tool](web-search.md) - Search the web for URLs
- [Tool Calling Guide](tool-calling.md) - Overview of all tools
