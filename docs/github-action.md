# GitHub Action

Mention `@joshu` in an issue or pull request comment and Joshu works on it in
GitHub Actions:

- **On an issue**: Joshu makes the changes on a new branch
  (`joshu/issue-<number>-<run>`), opens a pull request and replies with a
  summary.
- **On a pull request**: Joshu checks out the PR, commits its changes to the PR
  branch and replies.

Only the repository's owner, members and collaborators can trigger it.

## Setup

1. Add a model API key as a repository secret (Settings → Secrets and variables
   → Actions), e.g. `NVIDIA_API_KEY` (free from build.nvidia.com).
2. Add `.github/workflows/joshu.yml`:

```yaml
name: Joshu
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  joshu:
    if: >-
      contains(github.event.comment.body, '@joshu') &&
      contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association)
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: Faycalraghibi/Joshu@v0.3.0
        env:
          NVIDIA_API_KEY: ${{ secrets.NVIDIA_API_KEY }}
        with:
          provider: nvidia
```

Then comment, for example: `@joshu the date parser fails on ISO week dates,
please fix it and add a test`.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `trigger` | `@joshu` | Word that starts Joshu in a comment |
| `provider` | `nvidia` | Model provider; pass its key as an env var from a secret |
| `model` | provider default | Model id or named model |
| `permission_mode` | `accept_edits` | `accept_edits` (edits, no shell commands), `plan` (read-only, just answers) or `bypass` (also runs commands) |
| `max_turns` | `40` | Model calls per request |
| `max_budget_usd` | `0` | Stop when the run has cost this much (0 = no limit) |
| `max_request_tokens` | `0` | Stop after this many tokens (0 = no limit) |
| `joshu_version` | the action's source | A PyPI version to install instead |

Outputs: `result` (Joshu's answer) and `branch` (where its changes are).

## Notes

- Comments and issue text are passed to Joshu through environment variables,
  never pasted into shell commands.
- With `bypass`, Joshu can run any command in the runner; keep the default
  unless you trust everyone who can comment, and the issue content.
- Pull requests from forks can't receive pushes from the workflow token; Joshu
  then only replies.
- MCP servers are off in the action, and sessions aren't saved.
