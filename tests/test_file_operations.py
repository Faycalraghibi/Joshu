import tempfile
import unittest
from pathlib import Path

from joshu.tools.filesystem import (
    create_backup,
    find_files_by_extension,
    find_large_files,
    get_directory_structure,
    get_file_info,
    list_directory_contents,
    list_python_files,
)


class TestFileOperations(unittest.TestCase):
    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

        # Create test files and directories
        (self.test_path / "file1.py").write_text("print('hello')")
        (self.test_path / "file2.txt").write_text("test content")
        (self.test_path / "config.yaml").write_text("key: value")
        (self.test_path / "app.log").write_text("log content")

        # Create subdirectory with files
        subdir = self.test_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.py").write_text("print('world')")
        (subdir / "config.json").write_text('{"key": "value"}')

        # Create a "large" file for testing (actually small, but larger than threshold)
        large_file = self.test_path / "large_file.txt"
        large_file.write_text("x" * (15 * 1024 * 1024))  # 15MB file

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.test_dir)

    def test_list_python_files(self):
        """Test listing Python files."""
        python_files = list_python_files(self.test_dir)
        self.assertEqual(len(python_files), 2)
        python_file_names = [Path(f).name for f in python_files]
        self.assertIn("file1.py", python_file_names)
        self.assertIn("file3.py", python_file_names)

    def test_get_directory_structure(self):
        """Test getting directory structure."""
        structure = get_directory_structure(self.test_dir, max_depth=2)
        self.assertIsInstance(structure, dict)
        self.assertIn(Path(self.test_dir).name, structure)

    def test_find_files_by_extension(self):
        """Test finding files by extension."""
        yaml_files = find_files_by_extension(self.test_dir, ".yaml")
        self.assertEqual(len(yaml_files), 1)
        self.assertTrue(yaml_files[0].endswith("config.yaml"))

        # Test without dot prefix
        json_files = find_files_by_extension(self.test_dir, "json")
        self.assertEqual(len(json_files), 1)
        self.assertTrue(json_files[0].endswith("config.json"))

    def test_get_file_info(self):
        """Test getting file information."""
        file_path = str(self.test_path / "file1.py")
        file_info = get_file_info(file_path)
        self.assertIsNotNone(file_info)
        if file_info is not None:
            self.assertEqual(file_info.name, "file1.py")
            self.assertEqual(file_info.extension, ".py")
            self.assertFalse(file_info.is_directory)
            self.assertGreater(file_info.size, 0)

    def test_list_directory_contents(self):
        """Test listing directory contents."""
        contents = list_directory_contents(self.test_dir)
        self.assertGreater(len(contents), 0)

        # Check that we have both files and directories
        file_names = [f.name for f in contents]
        self.assertIn("file1.py", file_names)
        self.assertIn("subdir", file_names)

    def test_find_large_files(self):
        """Test finding large files."""
        large_files = find_large_files(self.test_dir, min_size_mb=10)
        self.assertEqual(len(large_files), 1)
        self.assertEqual(large_files[0].name, "large_file.txt")

    def test_create_backup(self):
        """Test creating a backup."""
        backup_dir = tempfile.mkdtemp()
        result = create_backup(self.test_dir, backup_dir)
        self.assertTrue(result)

        # Check that backup was created
        backup_path = Path(backup_dir) / Path(self.test_dir).name
        self.assertTrue(backup_path.exists())
        self.assertTrue((backup_path / "file1.py").exists())

        # Clean up backup
        import shutil

        shutil.rmtree(backup_dir)


if __name__ == "__main__":
    unittest.main()
