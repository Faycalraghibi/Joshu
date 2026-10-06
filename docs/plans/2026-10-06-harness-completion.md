# Completing the harness

Joshu is a model-agnostic coding-agent harness: the loop, tools, permissions,
context management, state, extensions and interfaces around whatever model is
configured. The pieces are in place; what is left is raising the hard-task
pass rate (about half with small models), control for unattended use, and the
ecosystem. Each step ships as its own pull request with tests; the ones meant
to raise the pass rate are measured on the hard benchmark tier against a
baseline.

## 0. Open items

- **0a. Self-review** (done, #60): one check of the work against the request
  before finishing, on by default (`self_review`). A smaller A/B comparison can
  follow with `--set self_review=false`.
- **0b. IDE integration**: connect `joshu.ide` to a VS Code extension or
  remove it. Waiting for a decision.

## 1. Know why hard tasks fail

- The agent saves the conversation after every tool round, so a run killed at
  the timeout (or a crash) keeps it.
- `benchmarks/run.py` keeps each run's conversation next to the results.
- `benchmarks/triage.py` gives each failed run one cause (provider error, no
  edits, out of time, out of turns, untested, gave up failing, missed cases)
  and signals (failed edits, test runs, compaction, the failing check).

Its counts decide the order of step 2.

## 2. Raise the pass rate

- **Repository map** (`core/repo_map.py`): a compact file tree with top-level
  symbols (Python `ast`, regex for JS/TS/Go), capped near 1,500 tokens, cached
  until files change, in the system prompt for small enough projects
  (`repo_map: auto | off`). Measured: turns and tokens before the first edit,
  pass rate.
- **Verification gate** (`core/verify.py`): detect the project's test command
  (pytest, `npm test`, `go test`, `cargo test`) or use `verify_command`; when
  code changed since the last test run, the harness runs it before the agent
  finishes and sends failures back, for a few rounds at most. Measured against
  self-review alone.
- **Planning** for multi-step tasks: a todo list before the first edit, kept
  up to date. Only if triage shows runs losing track.

## 3. Control and ecosystem

- **Spending limits**: `max_budget_usd` and `max_request_tokens` per request
  and session (setting, `joshu run` flag, SDK option); the loop stops cleanly
  with `stopped="budget"`.
- **Plugins**: `joshu plugin install <git-url|path>` for bundles of commands,
  skills, hooks and MCP servers (`joshu-plugin.yaml`; YAML because Python 3.10
  has no TOML reader), with list, update, enable, disable and remove, through
  the existing loaders (done).
- **Managed settings**: a read-only `managed-settings.yaml` in a system path,
  the highest config layer, able to lock settings; shown in `/doctor`.

## 4. Quality

- **Terminal tests**: `pyte` plus a pseudo-terminal to start `joshu` with a
  scripted model, send keys and check the screen (questions, shells viewer,
  diffs, approvals), and a manual checklist for Windows Terminal, conhost,
  mintty and macOS/Linux terminals.
- **Release** when decided.

## Order

1, then 2 (in the order triage suggests), spending limits, terminal tests,
plugins, managed settings.
