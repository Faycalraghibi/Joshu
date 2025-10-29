#!/usr/bin/env python3
"""
Test script to check OpenRouter integration with GLM model.
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add src to path so we can import opencli modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_openrouter():
    """Test OpenRouter integration with GLM model."""
    # Load .env file
    load_dotenv()
    
    # Check if GLM_API_KEY is set
    glm_key = os.getenv("GLM_API_KEY")
    if not glm_key:
        print("GLM_API_KEY is not set")
        return
    
    print(f"GLM_API_KEY is set (first 10 chars): {glm_key[:10]}...")
    
    # Test the OpenRouter integration
    from opencli.models.openrouter import chat_completion
    
    messages = [
        {"role": "user", "content": "list files in current directory"}
    ]
    
    print("Testing chat_completion with GLM model...")
    response = chat_completion(messages, model="z-ai/glm-4.5-air:free")
    
    if response:
        print(f"Response received: {response}")
    else:
        print("No response received")
        
    # Also test the translate function
    from opencli.models.openrouter import translate_command_with_openrouter
    
    print("Testing translate_command_with_openrouter...")
    result = translate_command_with_openrouter("list files in current directory")
    
    if result:
        print(f"Translation result: {result}")
    else:
        print("No translation result")

if __name__ == "__main__":
    test_openrouter()