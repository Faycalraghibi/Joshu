# Benchmarks

Small, realistic coding tasks for measuring how well Joshu works with a given
model: bug fixes, implementing from tests, multi-file renames, adding a CLI
flag or a feature, and edits inside nested code.

```bash
python benchmarks/run.py --list
python benchmarks/run.py --provider nvidia --model nvidia/nemotron-3.5-lightning-30b-a3b
python benchmarks/run.py --model fast --tasks fix-bug,off-by-one --repeat 3
```

Each run copies the task into a temporary directory and runs `joshu run` there
with a temporary `JOSHU_HOME` (a copy of your user config, MCP off unless
`--mcp`), so your own sessions and settings are untouched. API keys come from
the environment and the repository's `.env`.

By default the agent runs in `accept_edits` mode: it can read and edit files
but not run commands. `--permission-mode bypass` lets it run commands too (for
example its own tests); it then runs unattended, so only use it with tasks you
trust.

After the agent finishes, the task's hidden checks (`check/`) are copied in and
its `check` command decides pass or fail, so the agent can't change the tests
it is graded on. Results are printed and saved to `benchmarks/results/`.

## Adding a task

```
benchmarks/tasks/<name>/
  task.yaml   prompt: what to ask the agent
              check: command that exits 0 when the task is done
              timeout: seconds (optional, default 600)
  files/      the starting project
  check/      hidden test files
```

The check must fail on the starting files and pass with a correct solution.
