#!/usr/bin/env python3
"""
Demonstration script for the memory summary feature.
This script shows how to use the new memory summary feature.
"""

from joshu.core.context_provider import ContextProvider
from joshu.core.translate import translate_to_command

def demonstrate_memory_summary():
    """Demonstrate the memory summary feature."""
    print("=== Memory Summary Feature Demonstration ===\n")
    
    # Create a context provider
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info
    context_provider.set_system_info(get_detailed_system_info())
    
    # Add some conversation history
    context_provider.add_to_history("user", "Hello, can you help me with file operations?")
    context_provider.add_to_history("assistant", "Of course! I can help you with file operations. What do you need to do?")
    context_provider.add_to_history("user", "Show me how to list files in a directory")
    context_provider.add_to_history("assistant", "You can use the 'dir' command to list files in the current directory.")
    context_provider.add_to_history("user", "What about subdirectories?")
    context_provider.add_to_history("assistant", "Use 'dir /s' to list files in subdirectories as well.")
    
    # Add some memory entries
    context_provider.set_memory("user_preference", "prefers Windows command line")
    context_provider.set_memory("last_command", "dir")
    context_provider.set_memory("working_directory", "C:\\Users\\Demo\\Documents")
    
    print("Context has been set up with:")
    print("- 3 conversation exchanges")
    print("- 3 memory entries")
    from joshu.tools.system_info import get_detailed_system_info
    print(f"- System info: {get_detailed_system_info()}")
    print()
    
    # Test various ways of asking for memory/history
    test_prompts = [
        "show me the history",
        "tell me the conversation history",
        "what is the memory",
        "give me the context",
        "provide memory summary"
    ]
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"{i}. User: '{prompt}'")
        translation = translate_to_command(prompt, context_provider)
        if translation:
            print(f"   Assistant: {translation.explanation}")
            print(f"   Command: {translation.command}")
        else:
            print("   Assistant: I couldn't generate a response for that request.")
        print()

if __name__ == "__main__":
    demonstrate_memory_summary()