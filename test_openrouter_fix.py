#!/usr/bin/env python3
"""
Test script to check the OpenRouter fix.
"""

import sys
import os

# Add src to path so we can import opencli modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_openrouter_fix():
    """Test the OpenRouter fix."""
    from opencli.models.openrouter import translate_command_with_openrouter
    
    print("Testing OpenRouter translation fix...")
    result = translate_command_with_openrouter("can you take a look to my code base")
    
    if result:
        print(f"SUCCESS: Translation result: {result}")
        return result
    else:
        print("FAILED: No translation result")
        return None

if __name__ == "__main__":
    test_openrouter_fix()