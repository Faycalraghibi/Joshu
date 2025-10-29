#!/usr/bin/env python3
"""
Script to update Joshu configuration to use the GLM model.
"""

import os
import yaml
from pathlib import Path

def update_config():
    """Update the Joshu configuration to use the GLM model."""
    # Default config location: ~/.joshu/config.yaml
    config_path = Path.home() / ".joshu" / "config.yaml"
    
    if not config_path.exists():
        print(f"Config file not found at {config_path}")
        return False
    
    try:
        # Load existing config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Update model to GLM
        old_model = config.get('model', 'unknown')
        config['model'] = 'z-ai/glm-4.5-air:free'
        
        # Save updated config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"Successfully updated model from '{old_model}' to 'z-ai/glm-4.5-air:free'")
        return True
        
    except Exception as e:
        print(f"Error updating config: {e}")
        return False

if __name__ == "__main__":
    update_config()