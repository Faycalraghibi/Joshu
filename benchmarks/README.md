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

## Why runs failed

Each run's conversation is kept next to its results file
(`benchmarks/results/<stamp>-<model>/<task>-<n>.json`; the agent saves it after
every tool round, so runs killed at the timeout keep theirs too;
`--no-transcripts` turns this off). `triage.py` reads them and gives each
failed run a cause:

```bash
python benchmarks/triage.py            # the latest results
python benchmarks/triage.py --all      # passed runs too
python benchmarks/triage.py --json
```

| Cause | Meaning |
|---|---|
| provider error | The endpoint failed (not counted against the model) |
| no edits | Finished or stopped without changing a file |
| out of time | Killed at the task's timeout |
| out of turns | Stopped by `max_turns`, a loop or repeated denials |
| untested | Edited after its last test run, or never ran tests |
| gave up failing | Its own last test run failed and it finished anyway |
| missed cases | Its own tests passed, the hidden checks did not |

Next to the cause: turns, edits that applied and that failed, test runs and
whether the last passed, compaction, and the first failing hidden check.

## Comparing runs

Six tasks run once can't tell a real improvement from luck: one run more or
less moves the pass rate by 17 points. Run each task several times and
compare setups with `compare.py`, which pools repeated runs (`a.json+b.json`)
and gives the pass rate with a 95% interval per setup:

```bash
python benchmarks/run.py --tier hard --repeat 3 --set thinking=off
python benchmarks/run.py --tier hard --repeat 3 --set thinking=auto
python benchmarks/compare.py --label off --label auto results/<off>.json results/<auto>.json
```

Tasks whose pass count changed are marked `*`; the verdict says whether the
intervals overlap (if they do, the difference isn't shown yet: add runs).

The `Benchmark` workflow (Actions > Benchmark > Run workflow) runs the same
on GitHub with the tier, repeats, provider, model and settings you give it,
puts the triage table in the run summary and keeps the results as an
artifact. It needs the provider's API key as a repository secret
(`NVIDIA_API_KEY` for the default provider).

The hard tier has 16 tasks: bug fixes across several files
(billing-rounding, timesheet-bugs, booking-overlap, leaderboard-ranking,
shop-discount-codes), implementing from a docstring or a spec (ttl-lru-cache,
ini-parser, rate-limiter, semver-compare, json-path-get, markdown-table,
undo-redo, retry-decorator), a migration and a rename refactor
(migrate-http-client, rename-with-alias) and a new CLI subcommand
(cli-subcommand).

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
