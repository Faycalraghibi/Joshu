# Changelog

All notable changes to the Joshu project will be documented in this file.

### Added

- **Web Search Feature**: Complete web search integration powered by DuckDuckGo
  - `joshu search <query>` CLI command for quick web searches
  - `/search <query>` slash command in interactive mode
  - Rich terminal output with formatted results
  - Configuration options for enabling/disabling, result limits, and timeouts
  - Privacy-focused search with no API keys required
  - Comprehensive test coverage (31/31 tests passing)
  - Full documentation in `docs/web-search.md`

- **Search Handler**: New `search_handler.py` module providing:
  - Configuration-aware search execution
  - Rich formatting and error handling
  - Support for disabled state and missing dependencies
  - Agent-friendly result formatting

- **Configuration**:
  - `web_search_enabled`: Enable/disable web search (default: `true`)
  - `web_search_max_results`: Default max results (default: `5`)
  - `web_search_timeout`: Request timeout in seconds (default: `10`)

- **Tests**:
  - `test_web_search.py`: Core search functionality tests
  - `test_cli_search.py`: CLI command integration tests
  - `test_interactive_search.py`: Interactive mode slash command tests
  - Full backward compatibility testing

- **Documentation**:
  - Comprehensive web search guide with examples
  - Configuration documentation updates
  - README updates with search examples
  - API reference and troubleshooting guide

### Dependencies

- Added `duckduckgo-search>=6.0.0` to project dependencies

### Technical Details

- Implemented in `src/joshu/tools/web_search.py`
- CLI integration in `src/joshu/ui/cli.py`
- Handler in `src/joshu/ui/cli_handlers/search_handler.py`
- Interactive mode support in `src/joshu/ui/interactive/commands.py`
- Zero breaking changes - fully backward compatible

---

## [0.1.0] - Previous Release

### Initial Features

- Natural language to command translation
- Interactive chat mode with enhanced features
- Local LLM integration
- Command safety validation
- Code generation and editing
- Semantic memory system
- Translation caching
- Auto-fix for failed commands
- Session management
- Context-aware assistance
- Configurable settings

---

## Version History

This is the first changelog entry. Previous changes were tracked in commit history and documentation.

## Contributing

When adding new features, please update this changelog following the format above.

### Categories

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Features that will be removed
- **Removed**: Features that have been removed
- **Fixed**: Bug fixes
- **Security**: Security improvements
