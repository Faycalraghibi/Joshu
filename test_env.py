#!/usr/bin/env python3
"""
Test script to check if environment variables are loaded properly.
"""

import os
from dotenv import load_dotenv

def test_env():
    """Test if environment variables are loaded properly."""
    # Load .env file
    load_dotenv()
    
    # Check if OPENROUTER_API_KEY is set
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        print(f"OPENROUTER_API_KEY is set (first 10 chars): {api_key[:10]}...")
    else:
        print("OPENROUTER_API_KEY is not set")
    
    # Check if GLM_API_KEY is set
    glm_key = os.getenv("GLM_API_KEY")
    if glm_key:
        print(f"GLM_API_KEY is set (first 10 chars): {glm_key[:10]}...")
    else:
        print("GLM_API_KEY is not set")

if __name__ == "__main__":
    test_env()