#!/usr/bin/env python3
"""
Debug test script to check the OpenRouter fix.
"""

import sys
import os
import json

# Add src to path so we can import opencli modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_debug():
    """Debug the OpenRouter fix."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    print("Environment variables:")
    print(f"OPENROUTER_API_KEY: {os.getenv('OPENROUTER_API_KEY', 'Not set')[:10]}..." if os.getenv('OPENROUTER_API_KEY') else "Not set")
    print(f"OPENROUTER_MODEL: {os.getenv('OPENROUTER_MODEL', 'Not set')}")
    
    from opencli.models.openrouter import chat_completion, get_openrouter_client
    
    # Test the client creation
    model_name = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    print(f"\nUsing model: {model_name}")
    
    client = get_openrouter_client(model_name)
    if client:
        print("Client created successfully")
    else:
        print("Failed to create client")
        return
    
    # Test chat completion directly
    messages = [
        {"role": "user", "content": "can you take a look to my code base"}
    ]
    
    print("\nTesting chat completion...")
    response = chat_completion(messages, model=model_name, temperature=0.1, max_tokens=256)
    
    if response:
        print(f"Response received: {response}")
        
        # Test the JSON parsing
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
    else:
        print("No response received")
        return None

if __name__ == "__main__":
    test_debug()