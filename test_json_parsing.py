#!/usr/bin/env python3
"""
Test script to check JSON parsing fix.
"""

import sys
import os
import json

# Add src to path so we can import opencli modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_json_parsing():
    """Test the JSON parsing fix."""
    # Simulate the response from GLM model
    response = '''```json
{
  "command": "dir",
  "explanation": "Lists all files and directories in the current location, allowing you to see the structure of your code base."
}
```'''
    
    print("Testing JSON parsing with response:")
    print(repr(response))
    
    # Test the parsing logic
    cleaned_response = ""  # Initialize to avoid linter error
    try:
        # Clean up the response to handle markdown code blocks
        cleaned_response = response.strip()
        print(f"After strip: {repr(cleaned_response)}")
        
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
            print(f"After removing ```json: {repr(cleaned_response)}")
            
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
            print(f"After removing ```: {repr(cleaned_response)}")
            
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove ```
            print(f"After removing trailing ```: {repr(cleaned_response)}")
        
        # Strip any leading/trailing whitespace that might remain
        cleaned_response = cleaned_response.strip()
        print(f"After final strip: {repr(cleaned_response)}")
        
        # Parse JSON response
        data = json.loads(cleaned_response)
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        
        print(f"Command: {command}")
        print(f"Explanation: {explanation}")
        
        if command and explanation:
            print("SUCCESS: JSON parsing worked correctly!")
            return {"command": command, "explanation": explanation}
        else:
            print("FAILED: Command or explanation is missing")
            return None
            
    except json.JSONDecodeError as e:
        print(f"FAILED: JSON parsing error: {e}")
        print(f"Cleaned response was: {repr(cleaned_response)}")
        return None
    except Exception as e:
        print(f"FAILED: Unexpected error: {e}")
        return None

if __name__ == "__main__":
    test_json_parsing()