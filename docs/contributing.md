# Contributing

## Setup

```bash
git clone https://github.com/Faycalraghibi/Joshu.git
cd Joshu
python -m venv .joshuvenv
.joshuvenv\Scripts\activate  # Windows
pip install -e .[dev]
pre-commit install
```

## Development

```bash
# Run tests
pytest

# Code quality
ruff check src/ tests/
mypy src/
black src/ tests/
```

## Pull Requests

1. Fork & branch from `main`
2. Write tests for new features
3. Ensure all checks pass
4. Submit PR with clear description

## Code Style

- Follow existing patterns
- Type hints required
- Run `black` and `ruff` before committing
