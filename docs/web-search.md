# Web Search

Joshu includes built-in web search functionality that allows you to search the internet directly from the command line or interactive mode, powered by DuckDuckGo.

## Features

- **Privacy-focused**: Uses DuckDuckGo for private, anonymous searches
- **No API key required**: Works out of the box without registration
- **CLI and Interactive**: Available both as a command and in interactive mode
- **Configurable**: Control results count, timeouts, and enable/disable
- **Rich formatting**: Beautiful terminal output with result highlighting

## Installation

Web search uses the `ddgs` package (installed with Joshu):

```bash
pip install -e .
# or specifically
pip install ddgs
```

## Basic Usage

### CLI Command

Search directly from your terminal:

```bash
# Basic search
joshu search "Python best practices"

# Limit number of results
joshu search "machine learning tutorials" --max-results 10

# Search with quotes
joshu search "how to install docker"
```

### Interactive Mode

Use the `/search` slash command in interactive mode:

```bash
joshu interactive
```

Then in the interactive session:

```
> /search Python web frameworks
> /search latest AI news
> /search "git merge conflicts"
```

## Examples

### Example 1: Quick Information Lookup

```bash
$ joshu search "what is Docker"

🔍 Searching for: what is Docker

✓ Found 5 results:

╭─ Result 1 ─────────────────────────────────────────╮
│ Docker: Empowering App Development for Developers │
│ https://www.docker.com                            │
│                                                    │
│ Docker is a platform designed to help developers  │
│ build, share, and run containerized applications. │
╰────────────────────────────────────────────────────╯
```

### Example 2: Programming Help

```bash
$ joshu search "Python async await tutorial"
```

### Example 3: Interactive Research Session

```
$ joshu interactive

> /search FastAPI features
🔍 Searching for: FastAPI features
✓ Found 5 results...

> /search FastAPI vs Flask performance
🔍 Searching for: FastAPI vs Flask performance
✓ Found 5 results...
```

## Configuration

Web search behavior can be customized in `~/.joshu/config.yaml`:

```yaml
# Web search settings
web_search_enabled: true          # Enable/disable web search
web_search_max_results: 5         # Default max results
web_search_timeout: 10            # Request timeout (seconds)
```

### Configuration via CLI

```bash
# Disable web search
joshu config --set web_search_enabled=false

# Set default max results to 10
joshu config --set web_search_max_results=10

# Set timeout to 15 seconds
joshu config --set web_search_timeout=15

# View current settings
joshu config --get web_search_enabled
```

### Configuration in Code

```python
from joshu.core.config import get_config_manager

config = get_config_manager()

# Check if enabled
if config.get('web_search_enabled'):
    print("Web search is enabled")

# Get max results
max_results = config.get('web_search_max_results', 5)
```

## Advanced Usage

### Command-Line Flags

The `--max-results` flag overrides the configured default:

```bash
# Get 15 results instead of default 5
joshu search "Python tutorials" --max-results 15

# Get minimal results for quick answers
joshu search "current Python version" --max-results 3
```

### Multi-word Queries

Quotes are optional for multi-word queries:

```bash
# All equivalent
joshu search Python best practices
joshu search "Python best practices"
joshu search 'Python best practices'
```

### Special Characters

Queries support special characters and operators:

```bash
# Quotes for exact phrases
joshu search "error: module not found"

# URLs in queries
joshu search site:python.org decorators

# Technical searches
joshu search "TypeError: 'NoneType' object is not subscriptable"
```

## API Reference

### Search Function

```python
from joshu.tools.web_search import search_web

result = search_web(
    query="Python tutorials",
    max_results=5,
    timeout=10
)

# Result structure:
# {
#     "success": True/False,
#     "query": "original query",
#     "results": [
#         {
#             "title": "Result title",
#             "url": "https://...",
#             "snippet": "Description..."
#         }
#     ],
#     "error": None or error message
# }
```

### Format Results

```python
from joshu.tools.web_search import format_search_results

# Get formatted string for display
formatted = format_search_results(result)
print(formatted)
```

### Handler Function

```python
from joshu.ui.cli_handlers.search_handler import handle_search_command

# Execute search with all UI logic
handle_search_command(
    query="Python",
    max_results=10  # Optional, uses config if None
)
```

## Troubleshooting

### Library Not Installed

**Error**: `Web search library not installed`

**Solution**:
```bash
pip install ddgs
# or
pip install -e .
```

### Search Disabled

**Message**: `Web search is disabled in configuration`

**Solution**:
```bash
joshu config --set web_search_enabled=true
```

### No Results Found

If searches return no results:

1. Try different keywords or rephrase the query
2. Check your internet connection
3. Verify the query isn't too specific
4. Try a broader search term

### Timeout Errors

If searches timeout frequently:

```bash
# Increase timeout to 20 seconds
joshu config --set web_search_timeout=20
```

### Rate Limiting

DuckDuckGo may rate-limit excessive requests. If you encounter this:

1. Wait a few minutes before searching again
2. Reduce the frequency of searches
3. Use more specific queries to get better results with fewer searches

## Privacy & Security

### Privacy Features

- **No tracking**: DuckDuckGo doesn't track your searches
- **No API keys**: No account or registration required
- **No storage**: Search results are not stored locally
- **Direct queries**: Searches go directly to DuckDuckGo

### Data Usage

- Search queries are sent to DuckDuckGo servers
- Results are fetched and displayed immediately
- No persistent storage of search history
- No analytics or tracking within Joshu

## Integration with Agent

While the web search feature is primarily user-facing, it can be used in agent workflows:

```bash
# Agent can suggest searches
$ joshu "find information about Python 3.12 features"
Assistant: I can help you search for that information.
Suggested command: joshu search "Python 3.12 features"
```

## Best Practices

1. **Be specific**: More specific queries yield better results
   - Good: "Python FastAPI authentication tutorial"
   - Less good: "Python tutorial"

2. **Use quotes for exact phrases**: When you need exact matches
   ```bash
   joshu search "ModuleNotFoundError: No module named 'requests'"
   ```

3. **Limit results appropriately**: More isn't always better
   ```bash
   joshu search "quick answer query" --max-results 3
   joshu search "comprehensive research" --max-results 10
   ```

4. **Combine with other tools**: Use search to find documentation, then ask Joshu to explain
   ```
   > /search Python decorators official docs
   > explain how Python decorators work
   ```

## Keyboard Shortcuts

In interactive mode:

- Type `/search <query>` and press Enter to search
- Use `/help` to see all available commands including `/search`
- Results scroll automatically - no need for pagination

## Related Commands

- `/help` - Show all interactive commands
- `/history` - View command history
- `/config` - View or modify configuration
- `joshu --help` - View all CLI commands

## Future Enhancements

Planned features for future releases:

- Search result caching for repeated queries
- Integration with semantic memory for context-aware searches
- Custom search engines (Google, Bing, etc.)
- Search history tracking
- Filtering and sorting results
- Export results to file

## Support

For issues, questions, or feature requests:

1. Check this documentation first
2. Review the troubleshooting section
3. Check the main [README](../README.md)
4. Open an issue on GitHub
