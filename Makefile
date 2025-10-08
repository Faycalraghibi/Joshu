.PHONY: venv win-venv install test lint format run clean

venv:
	bash clean_install-dev.sh

win-venv:
	powershell -ExecutionPolicy Bypass -File .\clean_install-dev.ps1

install:
	pip install -e .

test:
	bash tests/run_tests.sh

lint:
	flake8 src/

format:
	black src/ tests/

run:
	opencli run "show disk usage of current directory" -y

clean:
	rm -rf .venv .OpenCLIvenv dist build *.egg-info .pytest_cache

