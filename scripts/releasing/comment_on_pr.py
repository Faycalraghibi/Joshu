#!/usr/bin/env python3
"""
comment_on_pr.py - Post status comments to GitHub PRs.

Purpose:
    Adds or updates comments on GitHub pull requests to communicate
    release status, build results, or other automated notifications.

Inputs:
    --pr NUMBER       Pull request number
    --message TEXT    Comment message (or template name)
    --template NAME   Use a predefined template
    --verbose         Enable verbose output

Outputs:
    - Comment posted to PR via GitHub CLI

Side Effects:
    - Posts comment to GitHub PR

Safety Considerations:
    - Uses GitHub CLI for authentication
    - Preview before posting (--dry-run)
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
        print(f"[comment_on_pr] {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"[comment_on_pr] ERROR: {message}", file=sys.stderr)


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"[comment_on_pr] ✓ {message}")


# Predefined message templates
TEMPLATES = {
    "release_started": """🚀 **Release Started**

A release workflow has been triggered for this PR.

Status: In Progress
""",
    "release_ready": """✅ **Release Ready**

This PR is ready for release!

- All checks passed
- Artifacts built successfully
- Version validated

Ready to merge and publish.
""",
    "release_failed": """❌ **Release Failed**

The release workflow encountered an error.

Please check the workflow logs for details.
""",
    "review_requested": """👀 **Review Requested**

This PR requires review before release.

Please review the changes and approve when ready.
""",
    "deployed": """🎉 **Deployed**

This release has been published!

Version: {version}
""",
}


def get_template(name: str, **kwargs) -> str:
    """Get a message template with optional variable substitution."""
    if name not in TEMPLATES:
        return None

    template = TEMPLATES[name]

    # Substitute any provided variables
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))

    return template


def post_comment(
    pr_number: int,
    message: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Post a comment to a GitHub PR."""
    if dry_run:
        log("DRY RUN: Would post comment:", True)
        print("-" * 40)
        print(message)
        print("-" * 40)
        return True

    cmd = [
        "gh",
        "pr",
        "comment",
        str(pr_number),
        "--body",
        message,
    ]

    log(f"Posting comment to PR #{pr_number}...", verbose)

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log_error(f"Failed to post comment: {result.stderr}")
        return False

    log_success(f"Posted comment to PR #{pr_number}")
    return True


def list_templates() -> None:
    """Print available templates."""
    print("Available templates:")
    print()
    for name, content in TEMPLATES.items():
        # Show first line as description
        first_line = content.strip().split("\n")[0]
        print(f"  {name:20} - {first_line}")
    print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Post status comments to GitHub PRs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/releasing/comment_on_pr.py --pr 123 --message "Build passed!"
    python scripts/releasing/comment_on_pr.py --pr 123 --template release_ready
    python scripts/releasing/comment_on_pr.py --list-templates
        """,
    )
    parser.add_argument(
        "--pr",
        type=int,
        help="Pull request number",
    )
    parser.add_argument(
        "--message",
        "-m",
        help="Comment message",
    )
    parser.add_argument(
        "--template",
        "-t",
        choices=list(TEMPLATES.keys()),
        help="Use a predefined template",
    )
    parser.add_argument(
        "--version",
        help="Version for template substitution",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List available templates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be posted without posting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Handle list-templates
    if args.list_templates:
        list_templates()
        return 0

    # Validate required arguments
    if not args.pr:
        log_error("--pr is required")
        return 1

    if not args.message and not args.template:
        log_error("Either --message or --template is required")
        return 1

    # Get message content
    if args.template:
        kwargs = {}
        if args.version:
            kwargs["version"] = args.version

        message = get_template(args.template, **kwargs)
        if not message:
            log_error(f"Unknown template: {args.template}")
            return 1
    else:
        message = args.message

    # Post comment
    if not post_comment(args.pr, message, args.dry_run, args.verbose):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
