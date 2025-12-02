# File Operations

## Overview

Joshu includes built-in filesystem utilities accessible through natural language or programmatically. These tools help with common file management tasks.

## Natural Language Usage

Just ask Jos hu for what you need:

```bash
# Find files
joshu "list all Python files"
joshu "find files larger than 10MB"
joshu "show directory structure"

# File information
joshu "get file info for config.yaml"
joshu "list directory contents"

# Backups
joshu "create backup of my project"
```

## Programmatic Usage

### List Python Files

Find all `.py` files recursively:

```python
from joshu.tools.filesystem import list_python_files

python_files = list_python_files("/path/to/directory")
for file in python_files:
    print(file)
```

**Returns**: List of absolute file paths

---

### Get Directory Structure

Get nested directory tree:

```python
from joshu.tools.filesystem import get_directory_structure

structure = get_directory_structure("/path/to/directory", max_depth=3)
print(structure)
```

**Parameters**:
- `directory` (str): Path to directory
- `max_depth` (int): Maximum recursion depth (default: unlimited)

**Returns**: Dict representing directory structure

---

### Find Files by Extension

Find files with specific extension:

```python
from joshu.tools.filesystem import find_files_by_extension

# Find YAML files
yaml_files = find_files_by_extension("/path/to/dir", ".yaml")

# Extension dot is optional
json_files = find_files_by_extension("/path/to/dir", "json")
```

**Parameters**:
- `directory` (str): Path to search
- `extension` (str): File extension (with or without dot)

**Returns**: List of matching file paths

---

### Get File Information

Get detailed file metadata:

```python
from joshu.tools.filesystem import get_file_info

info = get_file_info("/path/to/file.txt")
print(f"Name: {info.name}")
print(f"Extension: {info.extension}")
print(f"Size: {info.size} bytes")
print(f"Is directory: {info.is_directory}")
```

**Returns**: `FileInfo` object with:
- `name` (str): File name
- `extension` (str): File extension
- `size` (int): Size in bytes
- `is_directory` (bool): Whether it's a directory
- Other metadata (timestamps, permissions, etc.)

---

### List Directory Contents

List all files and subdirectories:

```python
from joshu.tools.filesystem import list_directory_contents

contents = list_directory_contents("/path/to/directory")
for item in contents:
    if item.is_directory:
        print(f"[DIR]  {item.name}")
    else:
        print(f"[FILE] {item.name} ({item.size} bytes)")
```

**Returns**: List of `FileInfo` objects

---

### Find Large Files

Find files above a size threshold:

```python
from joshu.tools.filesystem import find_large_files

# Find files larger than 100MB
large_files = find_large_files("/path/to/directory", min_size_mb=100)
for file in large_files:
    print(f"{file.name}: {file.size / (1024*1024):.2f} MB")
```

**Parameters**:
- `directory` (str): Path to search
- `min_size_mb` (int): Minimum file size in megabytes

**Returns**: List of `FileInfo` objects for large files

---

### Create Backup

Create directory backup:

```python
from joshu.tools.filesystem import create_backup

# Create backup in specific location
success = create_backup(
    source="/path/to/source",
    backup_dir="/path/to/backups"
)

if success:
    print("Backup created successfully")
```

**Parameters**:
- `source` (str): Directory to backup
- `backup_dir` (str): Where to store backup

**Returns**: `bool` indicating success

The backup will be created as a subdirectory in `backup_dir` with the same name as the source directory.

## Use Cases

### Find Old Log Files

```python
import os
from pathlib import Path
from joshu.tools.filesystem import find_files_by_extension

log_files = find_files_by_extension("/var/log", ".log")

# Filter by age
old_logs = []
for log_file in log_files:
    age_days = (time.time() - os.path.getmtime(log_file)) / 86400
    if age_days > 30:
        old_logs.append(log_file)
```

### Clean Up Large Files

```python
from joshu.tools.filesystem import find_large_files

# Find files > 1GB
huge_files = find_large_files("/path/to/check", min_size_mb=1024)

for file in huge_files:
    size_gb = file.size / (1024**3)
    print(f"Large file: {file.name} ({size_gb:.2f} GB)")
    # Review and potentially delete
```

### Organize Project Files

```python
from joshu.tools.filesystem import list_python_files, list_directory_contents

# Get all Python files
py_files = list_python_files("/project")

# Categorize by size
small_files = [f for f in py_files if os.path.getsize(f) < 10_000]
large_files = [f for f in py_files if os.path.getsize(f) >= 10_000]

print(f"Small Python files: {len(small_files)}")
print(f"Large Python files: {len(large_files)}")
```

### Pre-Deployment Backup

```python
from joshu.tools.filesystem import create_backup
from datetime import datetime

# Create timestamped backup
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_name = f"backup_{timestamp}"

create_backup(
    source="/app/production",
    backup_dir=f"/backups/{backup_name}"
)
```

## Best Practices

1. **Use Absolute Paths**: More reliable than relative paths
2. **Check Existence**: Verify paths exist before operations
3. **Handle Errors**: Wrap file operations in try-except
4. **Respect Permissions**: Ensure you have read/write access
5. **Test on Small Directories**: Before running on large trees

## Error Handling

```python
from joshu.tools.filesystem import get_file_info

try:
    info = get_file_info("/might/not/exist.txt")
    if info is None:
        print("File not found or inaccessible")
    else:
        print(f"File size: {info.size}")
except PermissionError:
    print("No permission to access file")
except Exception as e:
    print(f"Error: {e}")
```

## Related Documentation

- [CLI Reference](cli-reference.md) - Natural language file commands
- [Configuration](configuration.md) - File operation settings
- [Safety Features](safety.md) - File operation safety
