# Add Semantic Long-Term Memory System

## Overview

This PR introduces a semantic memory system that enables Joshu to recall relevant past conversations based on **semantic similarity** rather than just keyword matching or recency. This significantly improves the assistant's ability to maintain context across sessions and find relevant information from previous interactions.

## Motivation

Previously, Joshu relied on:
- **Recent conversation history** (limited window)
- **Key-value memory store** (requires exact key matches)
- **JSON file storage** (chronological queries only)

This meant that if a user mentioned "I prefer Python for data science" in a conversation a week ago, Joshu wouldn't remember it unless it was stored with an exact key match. The semantic memory system solves this by allowing Joshu to find relevant past conversations even when users phrase queries differently.

## Technical Implementation

### Core Components

1. **`SemanticMemory` class** (`src/joshu/core/storage/semantic_memory.py`)
   - Uses **ChromaDB** for local vector database storage
   - Uses **sentence-transformers** (all-MiniLM-L6-v2) for generating text embeddings
   - Stores conversation messages with metadata (role, session_id, timestamp)
   - Provides semantic search with similarity scoring

2. **Integration with `ContextProvider`**
   - Automatically stores messages in semantic memory when `add_to_history()` is called
   - Enhances `get_relevant_context()` to include semantically similar past conversations
   - Integrates with existing memory systems (doesn't replace them)

3. **Optional Dependencies**
   - Gracefully degrades if dependencies are not installed
   - System continues to work normally without semantic memory

### Key Features

- **Semantic Search**: Find relevant past conversations based on meaning, not keywords
- **Session Filtering**: Search within specific sessions or across all sessions
- **Role Filtering**: Filter by user or assistant messages
- **Similarity Scoring**: Configurable minimum similarity thresholds
- **Persistent Storage**: All memories persist across sessions using ChromaDB
- **Automatic Storage**: Messages are automatically stored when added to conversation history

### Architecture

```
ContextProvider
├── conversation_context (recent history)
├── memory_store (key-value memory)
└── semantic_memory (semantic vector search) ← NEW
    ├── ChromaDB (vector storage)
    └── SentenceTransformer (embeddings)
```

## Dependencies

### Optional Dependencies (New)

Added to `pyproject.toml` as an optional dependency group:

```toml
[project.optional-dependencies]
semantic = [
    "chromadb>=0.4.0",
    "sentence-transformers>=2.2.0"
]
```

**Installation:**
```bash
pip install -e ".[semantic]"
```

The system works without these dependencies - semantic memory will simply be disabled if not installed.

## Integration Points

### Automatic Storage

When messages are added to conversation history:
```python
context_provider.add_to_history("user", "I prefer Python for data science")
context_provider.add_to_history("assistant", "Great! Python is excellent for data science.")
```

Both messages are automatically stored in semantic memory (if enabled) and can later be retrieved via semantic search.

### Enhanced Context Retrieval

When `get_relevant_context()` is called:
1. Recent conversation history (last N messages)
2. Key-value memory entries
3. **Semantically similar past conversations** ← NEW

This provides much richer context to the LLM, enabling better responses that reference past conversations.

### Example Usage

```python
# Search for relevant past conversations
results = context_provider.semantic_memory.search(
    query="data analysis tools",
    limit=5,
    session_id=None,  # Search all sessions
    min_score=0.3     # Minimum similarity threshold
)

# Get formatted context for LLM
context = context_provider.semantic_memory.get_relevant_context(
    query="python libraries for ML",
    max_results=5
)
```

## Testing

Comprehensive test suite (`tests/test_semantic_memory.py`) covering:
- ✅ Initialization and graceful degradation without dependencies
- ✅ Adding and searching memories
- ✅ Session and role filtering
- ✅ Similarity scoring and minimum score thresholds
- ✅ Persistence across instances
- ✅ Integration with ContextProvider
- ✅ Windows file handle cleanup (retry logic for ChromaDB)

**All tests pass**, including Windows-specific file handle handling.

## File Changes

### New Files
- `src/joshu/core/storage/semantic_memory.py` - Core semantic memory implementation
- `tests/test_semantic_memory.py` - Comprehensive test suite

### Modified Files
- `src/joshu/core/context_provider.py` - Integrated semantic memory
- `src/joshu/core/storage/__init__.py` - Export semantic memory classes
- `pyproject.toml` - Added optional semantic dependencies
- `.gitignore` - Added ChromaDB directories

## Backward Compatibility

✅ **Fully backward compatible**
- System works exactly as before if optional dependencies are not installed
- No breaking changes to existing APIs
- Graceful degradation - semantic memory is simply disabled if dependencies unavailable

## Platform Support

✅ **Cross-platform** (Windows, Linux, macOS)
- Handles Windows file handle locking with retry logic
- Proper cleanup of ChromaDB resources
- Unique test directories to prevent conflicts

## Performance Considerations

- **Embedding Model**: Uses lightweight `all-MiniLM-L6-v2` model (~90MB, CPU-friendly)
- **Storage**: Local ChromaDB database (no external services)
- **Search**: Fast vector similarity search (typically <100ms)
- **Memory**: Embeddings are cached in memory for performance

## Future Enhancements

Potential improvements (not in this PR):
- Configurable embedding models
- Memory pruning/cleanup strategies
- Batch operations for bulk imports
- Export/import functionality
- Memory analytics and insights

## Migration Guide

No migration needed! The feature is opt-in via optional dependencies:

```bash
# To enable semantic memory
pip install -e ".[semantic]"

# System works fine without it
# pip install -e .
```

---

**Related Issues**: N/A (feature addition)

**Breaking Changes**: None

**Testing**: All existing tests pass, new test suite added
