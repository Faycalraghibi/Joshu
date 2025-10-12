import unittest
import tempfile
import os
from pathlib import Path
from opencli.core.config import ConfigManager, OpenCLIConfig, get_config_manager


class TestConfig(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test config
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = Path(self.test_dir) / "config.yaml"
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir)
    
    def test_config_creation(self):
        """Test creating OpenCLIConfig with default values."""
        config = OpenCLIConfig()
        self.assertEqual(config.model, "llama-3-8b")
        self.assertEqual(config.safety_mode, True)
        self.assertEqual(config.auto_execute, False)
        self.assertEqual(config.max_tokens, 4096)
        self.assertEqual(config.temperature, 0.1)
    
    def test_config_from_dict(self):
        """Test creating OpenCLIConfig from dictionary."""
        config_dict = {
            "model": "llama-3-70b",
            "safety_mode": False,
            "auto_execute": True,
            "max_tokens": 2048,
            "temperature": 0.5
        }
        config = OpenCLIConfig.from_dict(config_dict)
        self.assertEqual(config.model, "llama-3-70b")
        self.assertEqual(config.safety_mode, False)
        self.assertEqual(config.auto_execute, True)
        self.assertEqual(config.max_tokens, 2048)
        self.assertEqual(config.temperature, 0.5)
    
    def test_config_with_missing_keys(self):
        """Test creating OpenCLIConfig with missing keys uses defaults."""
        config_dict = {
            "model": "test-model"
            # Missing other keys should use defaults
        }
        config = OpenCLIConfig.from_dict(config_dict)
        self.assertEqual(config.model, "test-model")
        # Other values should be defaults
        self.assertEqual(config.safety_mode, True)
        self.assertEqual(config.auto_execute, False)
    
    def test_config_to_dict(self):
        """Test converting OpenCLIConfig to dictionary."""
        config = OpenCLIConfig(model="test-model", auto_execute=True)
        config_dict = config.to_dict()
        self.assertEqual(config_dict["model"], "test-model")
        self.assertEqual(config_dict["auto_execute"], True)
        self.assertEqual(config_dict["safety_mode"], True)
    
    def test_config_manager_creation(self):
        """Test creating ConfigManager."""
        config_manager = ConfigManager(str(self.test_config_path))
        self.assertEqual(config_manager.config_path, self.test_config_path)
        # Should have default config
        self.assertEqual(config_manager.config.model, "llama-3-8b")
    
    def test_config_manager_save_and_load(self):
        """Test saving and loading configuration."""
        # Create config manager and modify config
        config_manager = ConfigManager(str(self.test_config_path))
        config_manager.config.model = "test-model"
        config_manager.config.auto_execute = True
        
        # Save config
        self.assertTrue(config_manager.save_config())
        
        # Verify file was created
        self.assertTrue(self.test_config_path.exists())
        
        # Create new config manager to load config
        new_config_manager = ConfigManager(str(self.test_config_path))
        self.assertEqual(new_config_manager.config.model, "test-model")
        self.assertEqual(new_config_manager.config.auto_execute, True)
    
    def test_config_manager_get_set(self):
        """Test getting and setting configuration values."""
        config_manager = ConfigManager(str(self.test_config_path))
        
        # Test get
        self.assertEqual(config_manager.get("model"), "llama-3-8b")
        self.assertEqual(config_manager.get("nonexistent", "default"), "default")
        
        # Test set
        self.assertTrue(config_manager.set("model", "new-model"))
        self.assertEqual(config_manager.get("model"), "new-model")
        
        # Test setting invalid key
        self.assertFalse(config_manager.set("nonexistent", "value"))
    
    def test_config_manager_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        config_manager = ConfigManager(str(self.test_config_path))
        config_manager.config.model = "test-model"
        config_manager.config.auto_execute = True
        
        # Reset to defaults
        config_manager.reset_to_defaults()
        
        # Should be back to defaults
        self.assertEqual(config_manager.config.model, "llama-3-8b")
        self.assertEqual(config_manager.config.auto_execute, False)
    
    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton instance."""
        config_manager1 = get_config_manager()
        config_manager2 = get_config_manager()
        self.assertIs(config_manager1, config_manager2)


if __name__ == '__main__':
    unittest.main()