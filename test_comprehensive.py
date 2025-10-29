#!/usr/bin/env python3
"""
Comprehensive test script to check the OpenRouter fix.
"""

import sys
import os

# Add src to path so we can import opencli modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_comprehensive():
    """Test the OpenRouter fix with environment loading."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    print("Environment variables:")
    print(f"OPENROUTER_API_KEY: {os.getenv('OPENROUTER_API_KEY', 'Not set')[:10]}..." if os.getenv('OPENROUTER_API_KEY') else "Not set")
    print(f"OPENROUTER_MODEL: {os.getenv('OPENROUTER_MODEL', 'Not set')}")
    
    from opencli.models.openrouter import translate_command_with_openrouter
    
    print("\nTesting OpenRouter translation fix...")
    result = translate_command_with_openrouter("can you take a look to my code base")
    
    if result:
        print(f"SUCCESS: Translation result: {result}")
        return result
    else:
        print("FAILED: No translation result")
        return None

if __name__ == "__main__":
    test_comprehensive()