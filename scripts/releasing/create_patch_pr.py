#!/usr/bin/env python3
"""
create_patch_pr.py - Automate patch release workflow.

Purpose:
    Creates a patch release branch, cherry-picks specified commits,
    and opens a pull request for the patch release.

Inputs:
    --base TAG        Base version tag to branch from
    --commits COMMITS Comma-separated list of commit SHAs to cherry-pick
    --dry-run         Show what would happen without executing
    --verbose         Enable verbose output

Outputs:
    - New patch release branch
    - Pull request via GitHub CLI

Side Effects:
    - Creates git branch
    - Cherry-picks commits
    - Pushes to remote (with confirmation)
    - Creates GitHub PR

Safety Considerations:
    - Requires explicit confirmation before push
    - Supports dry-run mode for preview
    - Uses GitHub CLI for PR creation
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent.parent


def log(message: str, verbose: bool = True) -> None:
    """Print a log message if verbose mode is enabled."""
    if verbose:
        print(f"[create_patch_pr] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[create_patch_pr] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[create_patch_pr] ✓ {message}")


def log_warning(message: str) -> None:
    """Print a warning message."""
    print(f"[create_patch_pr] ⚠ {message}")


def run_git(args: list, dry_run: bool = False, verbose: bool = False) -> tuple:
    """Run a git command and return (success, output)."""
    cmd = ["git"] + args

    if dry_run:
        log(f"DRY RUN: {' '.join(cmd)}", True)
        return True, ""

    log(f"Running: {' '.join(cmd)}", verbose)

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    return result.returncode == 0, result.stdout + result.stderr


def check_tag_exists(tag: str) -> bool:
    """Check if a git tag exists."""
    success, _ = run_git(["rev-parse", tag])
    return success


def get_current_branch() -> str:
    """Get current branch name."""
    success, output = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return output.strip() if success else ""


def create_patch_branch(
    base_tag: str,
    branch_name: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Create patch release branch from base tag."""
    log(f"Creating branch {branch_name} from {base_tag}...", verbose)

    success, output = run_git(
        ["checkout", "-b", branch_name, base_tag],
        dry_run=dry_run,
        verbose=verbose,
    )

    if not success and not dry_run:
        log_error(f"Failed to create branch: {output}")
        return False

    log_success(f"Created branch: {branch_name}")
    return True


def cherry_pick_commits(
    commits: list,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Cherry-pick commits onto current branch."""
    for commit in commits:
        log(f"Cherry-picking {commit[:8]}...", verbose)

        success, output = run_git(
            ["cherry-pick", commit],
            dry_run=dry_run,
            verbose=verbose,
        )

        if not success and not dry_run:
            log_error(f"Failed to cherry-pick {commit}: {output}")
            log_error("You may need to resolve conflicts manually")
            return False

        log_success(f"Cherry-picked: {commit[:8]}")

    return True


def push_branch(
    branch_name: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Push branch to remote origin."""
    log(f"Pushing branch {branch_name} to origin...", verbose)

    success, output = run_git(
        ["push", "-u", "origin", branch_name],
        dry_run=dry_run,
        verbose=verbose,
    )

    if not success and not dry_run:
        log_error(f"Failed to push branch: {output}")
        return False

    log_success(f"Pushed branch: {branch_name}")
    return True


def create_pull_request(
    branch_name: str,
    base_branch: str,
    title: str,
    body: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Create pull request using GitHub CLI."""
    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        base_branch,
        "--head",
        branch_name,
        "--title",
        title,
        "--body",
        body,
    ]

    if dry_run:
        log(f"DRY RUN: {' '.join(cmd)}", True)
        return True

    log("Creating pull request...", verbose)

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log_error(f"Failed to create PR: {result.stderr}")
        return False

    log_success(f"Created PR: {result.stdout.strip()}")
    return True


def confirm_action(message: str) -> bool:
    """Ask for user confirmation."""
    response = input(f"{message} [y/N]: ").strip().lower()
    return response in ("y", "yes")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automate patch release workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/releasing/create_patch_pr.py --base v0.1.0 --commits abc123,def456
    python scripts/releasing/create_patch_pr.py --base v0.1.0 --commits abc123 --dry-run
        """,
    )
    parser.add_argument(
        "--base",
        "-b",
        required=True,
        help="Base version tag to branch from (e.g., v0.1.0)",
    )
    parser.add_argument(
        "--commits",
        "-c",
        required=True,
        help="Comma-separated list of commit SHAs to cherry-pick",
    )
    parser.add_argument(
        "--target-branch",
        default="main",
        help="Target branch for PR (default: main)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without executing",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)

    # Parse commits
    commits = [c.strip() for c in args.commits.split(",") if c.strip()]

    if not commits:
        log_error("No commits specified")
        return 1

    # Check base tag exists
    if not check_tag_exists(args.base):
        log_error(f"Base tag not found: {args.base}")
        return 1

    # Determine patch version
    base_version = args.base.lstrip("v")
    parts = base_version.split(".")
    if len(parts) >= 3:
        parts[2] = str(int(parts[2]) + 1)
        patch_version = ".".join(parts)
    else:
        patch_version = f"{base_version}.1"

    branch_name = f"release/v{patch_version}"

    print("\nPatch Release Plan:")
    print(f"  Base tag: {args.base}")
    print(f"  New version: v{patch_version}")
    print(f"  Branch: {branch_name}")
    print(f"  Commits: {len(commits)}")
    for commit in commits:
        print(f"    - {commit}")
    print()

    if not args.dry_run:
        if not confirm_action("Proceed with patch release?"):
            log_warning("Aborted by user")
            return 0

    # Step 1: Create branch
    if not create_patch_branch(args.base, branch_name, args.dry_run, args.verbose):
        return 1

    # Step 2: Cherry-pick commits
    if not cherry_pick_commits(commits, args.dry_run, args.verbose):
        return 1

    # Step 3: Push branch (with confirmation)
    if not args.dry_run:
        if not confirm_action(f"Push {branch_name} to origin?"):
            log_warning("Branch not pushed. You can push manually later.")
        else:
            if not push_branch(branch_name, args.dry_run, args.verbose):
                return 1
    else:
        push_branch(branch_name, args.dry_run, args.verbose)

    # Step 4: Create PR
    pr_title = f"Release v{patch_version}"
    pr_body = f"""## Patch Release v{patch_version}

This PR contains cherry-picked fixes from main for patch release v{patch_version}.

### Cherry-picked commits:
{chr(10).join(f"- {c}" for c in commits)}

### Checklist:
- [ ] All tests pass
- [ ] Version bumped
- [ ] Changelog updated
"""

    if not args.dry_run:
        if confirm_action("Create pull request?"):
            create_pull_request(
                branch_name,
                args.target_branch,
                pr_title,
                pr_body,
                args.dry_run,
                args.verbose,
            )
    else:
        create_pull_request(
            branch_name,
            args.target_branch,
            pr_title,
            pr_body,
            args.dry_run,
            args.verbose,
        )

    log_success("Patch release workflow complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
