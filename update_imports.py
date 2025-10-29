#!/usr/bin/env python3
"""
Script to update all import statements from opencli to joshu.
"""

import os
import re

def update_imports_in_file(file_path):
    """Update import statements in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace import statements
        updated_content = re.sub(r'from opencli\.', 'from joshu.', content)
        updated_content = re.sub(r'import opencli', 'import joshu', updated_content)
        
        # Replace references to OpenCLI in strings and comments
        updated_content = re.sub(r'OpenCLI', 'Joshu', updated_content)
        updated_content = re.sub(r'opencli', 'joshu', updated_content)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
            
        print(f"Updated {file_path}")
        return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def update_all_imports():
    """Update all import statements in the project."""
    # Get all Python files in the joshu directory
    for root, dirs, files in os.walk('src/joshu'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                update_imports_in_file(file_path)
    
    # Update demo files
    demo_files = [
        'demonstrate_config.py',
        'demonstrate_file_operations.py',
        'demonstrate_memory_summary.py',
        'demonstrate_model_switching.py',
        'demonstrate_safety_features.py'
    ]
    
    for file in demo_files:
        if os.path.exists(file):
            update_imports_in_file(file)
    
    # Update test files
    if os.path.exists('tests'):
        for root, dirs, files in os.walk('tests'):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    update_imports_in_file(file_path)

if __name__ == "__main__":
    update_all_imports()