#!/usr/bin/env python3
"""
Script to update the .env file to use the GLM model.
"""

import os

def update_env():
    """Update the .env file to use the GLM model."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_path):
        print(f"Env file not found at {env_path}")
        return False
    
    try:
        # Read the .env file
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Replace the OPENROUTER_MODEL line
        updated_content = content.replace(
            "OPENROUTER_MODEL='deepseek/deepseek-chat-v3.1:free'", 
            "OPENROUTER_MODEL='z-ai/glm-4.5-air:free'"
        )
        
        # Write back to the file
        with open(env_path, 'w') as f:
            f.write(updated_content)
        
        print("Successfully updated OPENROUTER_MODEL to 'z-ai/glm-4.5-air:free'")
        return True
        
    except Exception as e:
        print(f"Error updating .env file: {e}")
        return False

if __name__ == "__main__":
    update_env()