#!/usr/bin/env python3
"""
Demonstration script for the model switching feature.
This script shows how to use different LLM models with OpenCLI.
"""

from opencli.models.inference import get_model, list_loaded_models, unload_model, clear_model_cache
from opencli.core.context_provider import ContextProvider
from opencli.core.translate import translate_to_command

def demonstrate_model_switching():
    """Demonstrate the model switching feature."""
    print("=== Model Switching Feature Demonstration ===\n")
    
    # Show available models
    print("1. Available Models:")
    print("   - llama-3-8b (default local model)")
    print("   - llama-3-70b (larger local model)")
    print("   - mistral-7b (specialized local model)")
    print("   - codellama-34b (code-specialized model)")
    print("   - gemma-2-9b (efficient local model)")
    print("   - openai/gpt-4o (cloud model via OpenRouter)")
    print("   - openai/gpt-4o-mini (cloud model via OpenRouter)")
    print()
    
    # Demonstrate model caching
    print("2. Model Caching:")
    
    # Clear any existing cached models
    clear_model_cache()
    print(f"   Initially loaded models: {list_loaded_models()}")
    
    # Load a model
    model1 = get_model("llama-3-8b")
    print(f"   After loading 'llama-3-8b': {list_loaded_models()}")
    
    # Load the same model again (should return cached version)
    model1_again = get_model("llama-3-8b")
    print(f"   Loading 'llama-3-8b' again: Same object? {model1 is model1_again}")
    
    # Load a different model
    model2 = get_model("mistral-7b")
    print(f"   After loading 'mistral-7b': {list_loaded_models()}")
    print(f"   Different objects? {model1 is not model2}")
    
    # Unload a model
    unload_model("llama-3-8b")
    print(f"   After unloading 'llama-3-8b': {list_loaded_models()}")
    
    print()
    
    # Demonstrate translation with different models
    print("3. Translation with Different Models:")
    
    # Create a context provider
    context_provider = ContextProvider()
    context_provider.set_system_info("Windows 10")
    
    # Add some conversation history for context
    context_provider.add_to_history("user", "Show me how to list files")
    context_provider.add_to_history("assistant", "You can use the 'dir' command to list files in Windows")
    
    # Test translation with different models (using mocks since we don't have real models)
    print("   Note: In a real environment, you would see different translations based on the model capabilities")
    print("   For this demo, we're showing how the model parameter is passed through the system")
    
    # Show how the model parameter flows through the system
    print("   Command: translate_to_command('list all python files', context_provider, 'llama-3-70b')")
    print("   This would use the llama-3-70b model for translation")
    
    print()
    print("4. CLI Usage:")
    print("   You can now specify models when using the CLI:")
    print("   opencli run --model llama-3-8b \"list all python files\"")
    print("   opencli run --model mistral-7b \"explain what this regex does\"")
    print("   opencli run --model openai/gpt-4o \"debug this bash script\"")
    print()
    
    print("=== Demonstration Complete ===")

if __name__ == "__main__":
    demonstrate_model_switching()