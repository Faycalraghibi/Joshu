# Semantic Memory

Joshu's semantic memory system enables intelligent recall of past conversations based on meaning, not just recency.

## Overview

The semantic memory system uses:
- **ChromaDB** for vector storage
- **sentence-transformers** for text embeddings (all-MiniLM-L6-v2)
- Persistent storage across sessions

## Installation

Semantic memory requires optional dependencies:

```bash
pip install -e .[semantic]
```

This installs:
- `chromadb>=0.4.0`
- `sentence-transformers>=2.2.0`

## How It Works

### Automatic Storage

Conversations are automatically stored when:
1. User or assistant sends a message > 10 characters
2. Content is embedded using sentence-transformers
3. Vector embedding stored in ChromaDB
4. Associated with session ID and metadata

### Semantic Search

When searching with `/memory search <query>`:
1. Query is embedded using the same model
2. ChromaDB performs vector similarity search
3. Results ranked by cosine similarity
4. Only results above threshold returned
5. Limited to max_results (configurable)

## Commands

### Search Semantic Memory

```
/memory search <query>
```

**Example:**
```
> /memory search python machine learning

🔍 Found 3 relevant memories for: 'python machine learning'

1. [USER] [Session: 7f3a2b1c...] @ 2025-11-23 01:30:45
   I'm working on a Python project for machine learning

2. [ASSISTANT] [Session: 7f3a2b1c...] @ 2025-11-23 01:31:12
   For Python ML, scikit-learn is excellent...

3. [USER] [Session: 5d8e9a2f...] @ 2025-11-22 14:22:33
   What's the best way to implement neural networks?
```

### Show Memory Status

```
/memory status
```

**Output:**
```
📊 Semantic Memory Status:

  Status: ✅ Enabled
  Total memories: 847
  Embedding model: all-MiniLM-L6-v2
  Storage: ChromaDB (persistent)

  Configuration:
    - Similarity threshold: 0.3
    - Max results: 5
    - Min content length: 10
```

### Clear All Memories

```
/memory clear
```

**Output:**
```
✅ Cleared 847 semantic memories.
💡 New conversations will continue to be stored automatically.
```

## Configuration

### Config File

Add to `~/.joshu/config.yaml`:

```yaml
# Enable/disable semantic memory

# Similarity threshold (0.0-1.0)
# Lower = more results, higher = more precise
semantic_memory_similarity_threshold: 0.3

# Maximum results to return
semantic_memory_max_results: 5

# Minimum content length to store
semantic_memory_min_content_length: 10
```

### Environment Variables

```bash
# Not directly configurable via env vars
# Use config file or CLI
```

### CLI Configuration

```bash
# View settings
joshu config --get semantic_memory_max_results
joshu config --get semantic_memory_similarity_threshold

# Change settings
joshu config --set semantic_memory_similarity_threshold=0.5
joshu config --set semantic_memory_max_results=10
```

### In-Session Configuration

```
> /config semantic_memory_similarity_threshold 0.5
Set semantic_memory_similarity_threshold = 0.5

> /memory search programming
[Now uses 0.5 threshold]
```

## Storage Location

Semantic memories are stored in:

```
~/.joshu/.joshu_chromadb/      ($JOSHU_HOME/.joshu_chromadb/ when JOSHU_HOME is set)
```

This directory contains the ChromaDB database with all vector embeddings.

## Use Cases

### 1. Recall Past Solutions

```
> /memory search database migration problem

[Finds relevant past discussions about database migrations]
```

### 2. Find Related Conversations

```
> /memory search API authentication JWT

[Surfaces past conversations about authentication]
```

### 3. Context from Previous Sessions

```
> /memory search configuration nginx

[Retrieves nginx config discussions from any session]
```

## Advanced Features

### Session Filtering (Coming Soon)

```
/memory search <query> --session <session_id>
```

### Role Filtering (Coming Soon)

```
/memory search <query> --role user
/memory search <query> --role assistant
```

### Export/Import (Coming Soon)

```
/memory export memories.json
/memory import memories.json
```

## Performance

### Storage

- **~1KB per entry** (text + embeddings)
- **1000 entries ≈ 1MB** of storage
- Persistent across sessions

### Search Speed

- **\u003c100ms** for most searches
- Scales well to 10,000+ entries
- In-memory cache for frequently accessed data

## Troubleshooting

### Memory Not Working

1. **Check if enabled:**
   ```
   > /memory status
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .[semantic]
   ```

3. **Check logs:**
   ```bash
   joshu --log-level DEBUG interactive
   ```

### No Results Found

1. **Lower similarity threshold:**
   ```
   > /config semantic_memory_similarity_threshold 0.2
   ```

2. **Increase max results:**
   ```
   > /config semantic_memory_max_results 10
   ```

3. **Check if memories exist:**
   ```
   > /memory status
   ```

### Clear and Rebuild

If memory database is corrupted:

```bash
# Stop Joshu
# Delete database
rm -rf ~/.joshu/.joshu_chromadb/

# Restart Joshu
joshu interactive
# Memories will rebuild from conversations
```

## Implementation Details

### Embedding Model

**all-MiniLM-L6-v2:**
- 384-dimension embeddings
- Optimized for semantic similarity
- Fast inference (CPU-friendly)
- Balances accuracy and speed

### Storage Format

Each entry contains:
```json
{
  "id": "uuid",
  "content": "conversation text",
  "role": "user|assistant|system",
  "session_id": "session_uuid",
  "timestamp": 1700000000.0,
  "metadata": {}
}
```

### Integration with Context Provider

Semantic memories are automatically included in context via:

`context_provider.py`:
- Line 343-356: Automatic storage
- Line 494-508: Retrieval for context

## Next Steps

- **[Session Management](sessions.md)** — Managing conversation sessions
- **[Configuration](configuration.md)** — Advanced configuration
- **[API Reference](api-reference.md)** — Python API for semantic memory
