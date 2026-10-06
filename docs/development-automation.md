# Development Automation

The tools that run on Joshu's own code: what CI checks, how to run the same
checks locally, and how releases and benchmarks work.

## Quick Reference

| Task | Command |
|------|---------|
| Install for development | `pip install -e ".[dev]"` |
| Run the tests | `SKIP_LLM_TESTS=1 pytest` (Windows: `.\tests\run_tests.ps1`) |
| Lint (as CI does) | `python scripts/lint.py` |
| Fix lint and formatting | `python scripts/lint.py --fix` |
| Pre-commit hooks on every commit | `pre-commit install` |
| Check the benchmark tasks | `python benchmarks/run.py --verify` |
| Run the benchmark against a model | `python benchmarks/run.py --provider <p> --model <m>` |

## Pre-commit hooks

`.pre-commit-config.yaml` runs on each commit: trailing-whitespace and
end-of-file fixes, YAML and JSON checks, private-key detection, ruff (lint and
format), isort and mypy, and a hook that clears cache and session files from
the repository. Install them once with `pre-commit install`.

## Linting

`scripts/lint.py` is what CI runs. It finds the languages in the repository
and runs their linters; for Joshu that is ruff, ruff format (check) and mypy
for Python, yamllint for YAML and a JSON syntax check. `--fix` applies the
fixes the tools can make, and `--python` limits it to Python.

## CI workflows

| Workflow | When | What |
|---|---|---|
| `ci.yml` | every pull request and push to `main` | Lint; tests on Linux (Python 3.10 to 3.14) and Windows (3.13), with `SKIP_LLM_TESTS=1` |
| `release.yml` | a `v*` tag | Build the wheel and source archive, check the wheel installs, publish to PyPI with trusted publishing, create a GitHub release from the tag's `CHANGELOG.md` section |
| `joshu.yml` | an `@joshu` comment | The GitHub Action on Joshu's own repository (see [github-action.md](github-action.md)) |

## Tests

`SKIP_LLM_TESTS=1` makes every test that would reach a real model skip, so
the suite runs offline; tests use fake chat clients. The terminal tests in
`tests/e2e/` need `pywinpty` (Windows) or `pexpect` (elsewhere), both in the
`[dev]` extra. See the [testing guide](testing-guide.md).

## Benchmarks

`benchmarks/` holds coding tasks graded by hidden tests, in an easy and a hard
tier, with reference solutions for the hard tasks. `--verify` checks that
every task fails as given and passes when solved (a CI test runs it too). See
the docstring of `benchmarks/run.py` and "Choosing a model" in
[models-and-providers.md](models-and-providers.md).

## Releasing

1. Move the `[Unreleased]` entries in `CHANGELOG.md` under a new
   `[x.y.z] - date` heading and set `version` in `pyproject.toml`.
2. Merge, then tag: `git tag vx.y.z && git push origin vx.y.z`.
3. `release.yml` publishes to PyPI and creates the GitHub release.
