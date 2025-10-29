#!/usr/bin/env python3
"""
Script to fix OpenCLI configuration by updating the model to a working one.
"""

import os
import yaml
from pathlib import Path

def fix_config():
    """Fix the OpenCLI configuration by updating to a working model."""
    # Default config location: ~/.joshu/config.yaml
    config_path = Path.home() / ".joshu" / "config.yaml"
    
    if not config_path.exists():
        print(f"Config file not found at {config_path}")
        return False
    
    try:
        # Load existing config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Update model to a working one
        old_model = config.get('model', 'unknown')
        config['model'] = 'openai/gpt-4o-mini'
        
        # Save updated config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"Successfully updated model from '{old_model}' to 'openai/gpt-4o-mini'")
        return True
        
    except Exception as e:
        print(f"Error updating config: {e}")
        return False

if __name__ == "__main__":
    fix_config()