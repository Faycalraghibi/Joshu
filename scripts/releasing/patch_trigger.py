#!/usr/bin/env python3
"""
patch_trigger.py - Trigger patch release workflow and track progress.

Purpose:
    Dispatches GitHub Actions release workflow for patch releases,
    monitors workflow status, and posts progress updates to PRs.

Inputs:
    --pr NUMBER       PR number to comment on
    --version VER     Version being released
    --commits SHA     Comma-separated commit SHAs
    --workflow FILE   Workflow file name (default: release.yml)
    --dry-run         Preview actions without executing
    --verbose         Enable verbose output

Outputs:
    - Triggered workflow run
    - Status comments on PR

Side Effects:
    - Dispatches GitHub Actions workflow
    - Posts comments to GitHub PR

Safety Considerations:
    - Requires GITHUB_TOKEN environment variable
    - Use --dry-run to preview actions
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent.parent

DEFAULT_WORKFLOW = "release.yml"
POLL_INTERVAL = 30  # seconds
MAX_POLL_ATTEMPTS = 60  # 30 minutes max wait


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[patch_trigger] {message}")


def log_error(message: str) -> None:
    print(f"[patch_trigger] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    print(f"[patch_trigger] ✓ {message}")


def log_warning(message: str) -> None:
    print(f"[patch_trigger] ⚠ {message}")


# =============================================================================
# GitHub CLI Helpers
# =============================================================================


def check_gh_cli() -> bool:
    """Check if GitHub CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_repo_info() -> tuple[str, str]:
    """Get owner/repo from git remote."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data["owner"]["login"], data["name"]
    except Exception:
        pass
    return "", ""


# =============================================================================
# Workflow Dispatch
# =============================================================================


def dispatch_workflow(
    workflow: str,
    version: str,
    commits: str,
    pr_number: int,
    dry_run: bool = False,
    verbose: bool = False,
) -> Optional[int]:
    """
    Dispatch release workflow with inputs.
    Returns workflow run ID or None on failure.
    """
    cmd = [
        "gh",
        "workflow",
        "run",
        workflow,
        "-f",
        f"version={version}",
        "-f",
        f"commits={commits}",
        "-f",
        f"pr_number={pr_number}",
    ]

    log(f"Dispatching workflow: {workflow}", verbose)
    log(f"  Version: {version}", verbose)
    log(f"  Commits: {commits}", verbose)
    log(f"  PR: #{pr_number}", verbose)

    if dry_run:
        log(f"[DRY RUN] Would run: {' '.join(cmd)}", True)
        return 0

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        log_error(f"Failed to dispatch workflow: {result.stderr}")
        return None

    log_success("Workflow dispatched successfully")

    # Get the run ID (most recent run of this workflow)
    time.sleep(2)  # Give GitHub a moment to register the run

    try:
        result = subprocess.run(
            ["gh", "run", "list", "-w", workflow, "--limit", "1", "--json", "databaseId"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            runs = json.loads(result.stdout)
            if runs:
                return runs[0]["databaseId"]
    except Exception as e:
        log(f"Could not get run ID: {e}", verbose)

    return None


def get_workflow_status(run_id: int) -> tuple[str, str]:
    """
    Get workflow run status and conclusion.
    Returns (status, conclusion).
    """
    try:
        result = subprocess.run(
            ["gh", "run", "view", str(run_id), "--json", "status,conclusion"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("status", "unknown"), data.get("conclusion", "")
    except Exception:
        pass
    return "unknown", ""


def wait_for_workflow(
    run_id: int,
    verbose: bool = False,
) -> tuple[bool, str]:
    """
    Poll workflow status until complete.
    Returns (success, conclusion).
    """
    log(f"Waiting for workflow run {run_id}...", verbose)

    for attempt in range(MAX_POLL_ATTEMPTS):
        status, conclusion = get_workflow_status(run_id)

        if status == "completed":
            if conclusion == "success":
                log_success("Workflow completed successfully")
                return True, conclusion
            else:
                log_error(f"Workflow failed: {conclusion}")
                return False, conclusion

        log(f"Status: {status} (attempt {attempt + 1}/{MAX_POLL_ATTEMPTS})", verbose)
        time.sleep(POLL_INTERVAL)

    log_warning("Timeout waiting for workflow")
    return False, "timeout"


# =============================================================================
# PR Comments
# =============================================================================


def post_pr_comment(
    pr_number: int,
    message: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Post a comment to a pull request."""
    cmd = [
        "gh",
        "pr",
        "comment",
        str(pr_number),
        "--body",
        message,
    ]

    if dry_run:
        log(f"[DRY RUN] Would post to PR #{pr_number}:", True)
        print(message)
        return True

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        log_error(f"Failed to post comment: {result.stderr}")
        return False

    log_success(f"Posted comment to PR #{pr_number}")
    return True


def format_trigger_comment(
    version: str,
    workflow: str,
    run_id: Optional[int],
) -> str:
    """Format initial trigger comment."""
    owner, repo = get_repo_info()
    run_url = f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if run_id else "N/A"

    return f"""## 🚀 Patch Release Triggered

| Property | Value |
|----------|-------|
| Version | `{version}` |
| Workflow | `{workflow}` |
| Run | [{run_id}]({run_url}) |

The release workflow has been dispatched. I'll update this PR when it completes.

---
*Triggered by `patch_trigger.py`*
"""


def format_completion_comment(
    version: str,
    success: bool,
    conclusion: str,
    run_id: Optional[int],
) -> str:
    """Format completion comment."""
    owner, repo = get_repo_info()
    run_url = f"https://github.com/{owner}/{repo}/actions/runs/{run_id}" if run_id else "N/A"

    if success:
        return f"""## ✅ Patch Release Complete

| Property | Value |
|----------|-------|
| Version | `{version}` |
| Status | **Success** |
| Run | [{run_id}]({run_url}) |

The patch release `{version}` has been published successfully! 🎉

---
*Reported by `patch_trigger.py`*
"""
    else:
        return f"""## ❌ Patch Release Failed

| Property | Value |
|----------|-------|
| Version | `{version}` |
| Status | **{conclusion.upper()}** |
| Run | [{run_id}]({run_url}) |

The release workflow failed. Please check the [workflow logs]({run_url}) for details.

### Next Steps

1. Review the workflow logs for errors
2. Fix any issues in the codebase
3. Re-trigger with: `python scripts/releasing/patch_trigger.py --pr {run_id or "NUMBER"} --version {version}`

---
*Reported by `patch_trigger.py`*
"""


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trigger patch release workflow and track progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/releasing/patch_trigger.py --pr 123 --version 0.1.1
    python scripts/releasing/patch_trigger.py --pr 123 --version 0.1.1 --commits abc123,def456
    python scripts/releasing/patch_trigger.py --pr 123 --version 0.1.1 --dry-run
        """,
    )
    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="PR number to comment on",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Version being released",
    )
    parser.add_argument(
        "--commits",
        default="",
        help="Comma-separated commit SHAs (optional)",
    )
    parser.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help=f"Workflow file name (default: {DEFAULT_WORKFLOW})",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for workflow completion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without executing",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Check GitHub CLI
    if not args.dry_run and not check_gh_cli():
        log_error("GitHub CLI (gh) not found or not authenticated")
        log_error("Install: https://cli.github.com/")
        log_error("Auth: gh auth login")
        return 1

    print("=" * 60)
    print("Patch Release Trigger")
    print("=" * 60)

    # Dispatch workflow
    run_id = dispatch_workflow(
        workflow=args.workflow,
        version=args.version,
        commits=args.commits,
        pr_number=args.pr,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    if run_id is None and not args.dry_run:
        return 1

    # Post initial comment
    trigger_comment = format_trigger_comment(
        version=args.version,
        workflow=args.workflow,
        run_id=run_id,
    )
    post_pr_comment(args.pr, trigger_comment, args.dry_run, args.verbose)

    # Wait for completion (unless --no-wait)
    if not args.no_wait and run_id and not args.dry_run:
        success, conclusion = wait_for_workflow(run_id, args.verbose)

        # Post completion comment
        completion_comment = format_completion_comment(
            version=args.version,
            success=success,
            conclusion=conclusion,
            run_id=run_id,
        )
        post_pr_comment(args.pr, completion_comment, args.dry_run, args.verbose)

        return 0 if success else 1

    print("=" * 60)
    log_success("Patch trigger complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
