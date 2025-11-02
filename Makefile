.PHONY: venv win-venv install install-dev install-llm install-all test lint format run clean

# Create virtual environment (Linux/Unix)
venv:
	bash clean_install.sh

# Create virtual environment (Windows)
win-venv:
	powershell -ExecutionPolicy Bypass -File .\clean_install.ps1

# Install package (runtime only)
install:
	pip install -e .

# Install with dev dependencies
install-dev:
	pip install -e .[dev]

# Install with LLM dependencies
install-llm:
	pip install -e .[llm]

# Install with all optional dependencies
install-all:
	pip install -e .[dev,llm]

# Run tests
test:
	bash tests/run_tests.sh

# Lint code
lint:
	flake8 src/

# Format code
format:
	black src/ tests/

# Run example command
run:
	joshu run "show disk usage of current directory" -y

# Clean build artifacts
clean:
	rm -rf .venv .joshuvenv dist build *.egg-info .pytest_cache

