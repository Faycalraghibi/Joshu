#!/usr/bin/env python3
"""
Demonstration script for OpenCLI Configuration Management Features
"""

import tempfile
import os
from pathlib import Path
from opencli.core.config import ConfigManager, OpenCLIConfig


def demonstrate_config_features():
    """Demonstrate the configuration management features."""
    
    print("=== OpenCLI Configuration Management Features Demonstration ===\n")
    
    # Create a temporary directory for test config
    test_dir = tempfile.mkdtemp()
    test_config_path = Path(test_dir) / "config.yaml"
    
    try:
        # 1. Create ConfigManager
        print("1. Creating ConfigManager...")
        config_manager = ConfigManager(str(test_config_path))
        print(f"   Config path: {config_manager.get_config_path()}")
        print(f"   Default model: {config_manager.get('model')}")
        print()
        
        # 2. Show default configuration
        print("2. Default configuration:")
        config_dict = config_manager.config.to_dict()
        for key, value in config_dict.items():
            print(f"   {key}: {value}")
        print()
        
        # 3. Modify configuration
        print("3. Modifying configuration...")
        config_manager.set("model", "llama-3-70b")
        config_manager.set("auto_execute", True)
        config_manager.set("temperature", 0.3)
        print("   Set model to 'llama-3-70b'")
        print("   Set auto_execute to True")
        print("   Set temperature to 0.3")
        print()
        
        # 4. Save configuration
        print("4. Saving configuration...")
        if config_manager.save_config():
            print("   Configuration saved successfully!")
        else:
            print("   Failed to save configuration!")
        print()
        
        # 5. Load configuration
        print("5. Loading configuration...")
        new_config_manager = ConfigManager(str(test_config_path))
        print(f"   Loaded model: {new_config_manager.get('model')}")
        print(f"   Loaded auto_execute: {new_config_manager.get('auto_execute')}")
        print(f"   Loaded temperature: {new_config_manager.get('temperature')}")
        print()
        
        # 6. Get specific values
        print("6. Getting specific configuration values:")
        model = new_config_manager.get("model")
        max_tokens = new_config_manager.get("max_tokens")
        print(f"   model: {model}")
        print(f"   max_tokens: {max_tokens}")
        print()
        
        # 7. Reset to defaults
        print("7. Resetting to defaults...")
        new_config_manager.reset_to_defaults()
        print(f"   Model after reset: {new_config_manager.get('model')}")
        print(f"   Auto execute after reset: {new_config_manager.get('auto_execute')}")
        print()
        
        # 8. Show configuration file content
        print("8. Configuration file content:")
        if test_config_path.exists():
            with open(test_config_path, 'r') as f:
                content = f.read()
                print(content)
        
    finally:
        # Clean up
        import shutil
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    demonstrate_config_features()