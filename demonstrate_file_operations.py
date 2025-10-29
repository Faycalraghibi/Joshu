#!/usr/bin/env python3
"""
Demonstration script for Joshu File Operations Features
"""

import os
import tempfile
from pathlib import Path
from joshu.tools.filesystem import (
    list_python_files,
    get_directory_structure,
    find_files_by_extension,
    list_directory_contents,
    find_large_files,
    create_backup
)


def demonstrate_file_operations():
    """Demonstrate the file operations features."""
    
    print("=== Joshu File Operations Features Demonstration ===\n")
    
    # Create a temporary directory structure for demonstration
    test_dir = tempfile.mkdtemp()
    test_path = Path(test_dir)
    backup_dir = None
    
    try:
        # Create test files and directories
        (test_path / "main.py").write_text("print('Main application')")
        (test_path / "utils.py").write_text("def helper(): pass")
        (test_path / "README.md").write_text("# Project README")
        (test_path / "config.yaml").write_text("debug: true")
        (test_path / "app.log").write_text("Application started")
        
        # Create subdirectory with files
        subdir = test_path / "src"
        subdir.mkdir()
        (subdir / "module.py").write_text("def function(): pass")
        
        # Create a "large" file for testing
        large_file = test_path / "data.bin"
        large_file.write_text("x" * (5 * 1024 * 1024))  # 5MB file
        
        print(f"Created test directory: {test_dir}\n")
        
        # 1. List Python files
        print("1. Finding all Python files:")
        python_files = list_python_files(str(test_path))
        for file in python_files:
            print(f"   - {file}")
        print()
        
        # 2. Show directory structure
        print("2. Directory structure:")
        structure = get_directory_structure(str(test_path), max_depth=3)
        import json
        print(json.dumps(structure, indent=2))
        print()
        
        # 3. Find configuration files
        print("3. Finding configuration files:")
        config_extensions = ['.yaml', '.yml', '.json', '.ini', '.conf']
        config_files = []
        for ext in config_extensions:
            config_files.extend(find_files_by_extension(str(test_path), ext))
        for file in config_files:
            print(f"   - {file}")
        print()
        
        # 4. List directory contents
        print("4. Contents of test directory:")
        contents = list_directory_contents(str(test_path))
        for item in contents:
            if item.is_directory:
                print(f"   d {item.name}/")
            else:
                print(f"   f {item.name} ({item.size} bytes)")
        print()
        
        # 5. Find large files
        print("5. Large files (over 1MB):")
        large_files = find_large_files(str(test_path), min_size_mb=1)
        for file in large_files:
            print(f"   - {file.name}: {file.size} bytes")
        print()
        
        # 6. Create backup
        print("6. Creating backup:")
        backup_dir = tempfile.mkdtemp()
        success = create_backup(str(test_path), backup_dir)
        if success:
            print(f"   Backup created successfully in {backup_dir}")
        else:
            print("   Backup failed")
        print()
        
    finally:
        # Clean up
        import shutil
        shutil.rmtree(test_dir)
        # Clean up backup if it exists
        if backup_dir:
            try:
                shutil.rmtree(backup_dir)
            except:
                pass


if __name__ == "__main__":
    demonstrate_file_operations()