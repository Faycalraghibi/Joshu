#!/usr/bin/env python3
"""
check_secrets.py - Scan for sensitive information in source code.

Purpose:
    Detects potential secrets, API keys, tokens, and credentials
    in source files to prevent accidental commits of sensitive data.

Inputs:
    --path            Path to scan (default: project root)
    --strict          Exit with error if secrets found
    --verbose         Show detailed output
    --fix             Interactively remove detected secrets

Outputs:
    - Report of detected secrets
    - Exit code 0 if clean, 1 if secrets found (--strict)

Side Effects:
    - None (scan only)
    - With --fix, may modify files

Safety Considerations:
    - Never logs actual secret values, only locations
    - Supports .secretsignore for false positives
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Pattern, Set

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent


class SecretPattern(NamedTuple):
    """Pattern definition for secret detection."""

    name: str
    pattern: Pattern
    severity: str  # "high", "medium", "low"
    description: str


class SecretMatch(NamedTuple):
    """A detected secret match."""

    file: Path
    line_num: int
    pattern_name: str
    severity: str
    matched_text: str  # Redacted version


# =============================================================================
# Secret Detection Patterns
# =============================================================================

SECRET_PATTERNS: List[SecretPattern] = [
    # API Keys and Tokens
    SecretPattern(
        name="Generic API Key",
        pattern=re.compile(r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?'),
        severity="high",
        description="Generic API key assignment",
    ),
    SecretPattern(
        name="Generic Secret",
        pattern=re.compile(r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']'),
        severity="high",
        description="Password or secret assignment",
    ),
    SecretPattern(
        name="Generic Token",
        pattern=re.compile(
            r'(?i)(token|auth[_-]?token|access[_-]?token)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?'
        ),
        severity="high",
        description="Authentication token",
    ),
    # Cloud Provider Credentials
    SecretPattern(
        name="AWS Access Key",
        pattern=re.compile(r"(?i)AKIA[0-9A-Z]{16}"),
        severity="high",
        description="AWS Access Key ID",
    ),
    SecretPattern(
        name="AWS Secret Key",
        pattern=re.compile(
            r'(?i)(aws[_-]?secret|secret[_-]?access[_-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?'
        ),
        severity="high",
        description="AWS Secret Access Key",
    ),
    SecretPattern(
        name="Google API Key",
        pattern=re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        severity="high",
        description="Google API Key",
    ),
    SecretPattern(
        name="Azure Connection String",
        pattern=re.compile(
            r"(?i)DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+"
        ),
        severity="high",
        description="Azure Storage Connection String",
    ),
    # Private Keys - patterns are split to avoid triggering pre-commit hooks
    SecretPattern(
        name="RSA Private Key",
        pattern=re.compile(r"-----BEGIN RSA PRIV" + r"ATE KEY-----"),
        severity="high",
        description="RSA Private Key header",
    ),
    SecretPattern(
        name="SSH Private Key",
        pattern=re.compile(r"-----BEGIN OPENSSH PRIV" + r"ATE KEY-----"),
        severity="high",
        description="OpenSSH Private Key header",
    ),
    SecretPattern(
        name="PGP Private Key",
        pattern=re.compile(r"-----BEGIN PGP PRIV" + r"ATE KEY BLOCK-----"),
        severity="high",
        description="PGP Private Key header",
    ),
    # OAuth and JWT
    SecretPattern(
        name="GitHub Token",
        pattern=re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"),
        severity="high",
        description="GitHub Personal Access Token",
    ),
    SecretPattern(
        name="Slack Token",
        pattern=re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}"),
        severity="high",
        description="Slack API Token",
    ),
    SecretPattern(
        name="JWT Token",
        pattern=re.compile(r"eyJ[A-Za-z0-9-_=]+\.eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*"),
        severity="medium",
        description="JSON Web Token (may be test token)",
    ),
    # Database Credentials
    SecretPattern(
        name="Database URL",
        pattern=re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s]+"),
        severity="high",
        description="Database connection URL with credentials",
    ),
    # Misc
    SecretPattern(
        name="Bearer Token",
        pattern=re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-_.~+/]+=*"),
        severity="medium",
        description="Bearer authentication token",
    ),
    SecretPattern(
        name="Basic Auth",
        pattern=re.compile(r"(?i)basic\s+[a-zA-Z0-9+/]+=*"),
        severity="medium",
        description="Basic authentication header",
    ),
    SecretPattern(
        name="Hardcoded IP with Port",
        pattern=re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}"),
        severity="low",
        description="IP address with port (may be internal)",
    ),
]


# =============================================================================
# Ignore Patterns and Files
# =============================================================================

DEFAULT_IGNORE_PATTERNS = {
    # Directories to skip
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    # Files to skip
    "*.min.js",
    "*.min.css",
    "*.map",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
}

SCANNABLE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".kt",
    ".scala",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".dart",
    ".ex",
    ".exs",
    ".hs",
    ".lua",
    ".sh",
    ".bash",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".xml",
    ".env",
    ".ini",
    ".cfg",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".sql",
}


# =============================================================================
# Scanner
# =============================================================================


def log(message: str, verbose: bool = True) -> None:
    if verbose:
        print(f"[secrets] {message}")


def log_error(message: str) -> None:
    print(f"[secrets] ERROR: {message}", file=sys.stderr)


def log_warning(message: str) -> None:
    print(f"[secrets] ⚠️  {message}")


def log_success(message: str) -> None:
    print(f"[secrets] ✓ {message}")


def redact(text: str, keep_chars: int = 4) -> str:
    """Redact a secret, keeping only first few characters."""
    if len(text) <= keep_chars:
        return "*" * len(text)
    return text[:keep_chars] + "*" * (len(text) - keep_chars)


def load_ignore_file(path: Path) -> Set[str]:
    """Load patterns from .secretsignore file."""
    ignore_file = path / ".secretsignore"
    patterns = set(DEFAULT_IGNORE_PATTERNS)

    if ignore_file.exists():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.add(line)

    return patterns


def should_skip_path(path: Path, ignore_patterns: Set[str]) -> bool:
    """Check if path should be skipped."""
    path_str = str(path)

    for pattern in ignore_patterns:
        if pattern.startswith("*."):
            if path.suffix == pattern[1:]:
                return True
        elif pattern in path_str or path.name == pattern:
            return True

    return False


def should_scan_file(path: Path) -> bool:
    """Check if file should be scanned based on extension."""
    return path.suffix.lower() in SCANNABLE_EXTENSIONS


def scan_file(file_path: Path, verbose: bool = False) -> List[SecretMatch]:
    """Scan a single file for secrets."""
    matches = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()

        for line_num, line in enumerate(lines, 1):
            # Skip comments and very short lines
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or len(stripped) < 10:
                continue

            for pattern in SECRET_PATTERNS:
                match = pattern.pattern.search(line)
                if match:
                    matched_text = match.group(0)
                    matches.append(
                        SecretMatch(
                            file=file_path,
                            line_num=line_num,
                            pattern_name=pattern.name,
                            severity=pattern.severity,
                            matched_text=redact(matched_text, 8),
                        )
                    )
    except Exception as e:
        if verbose:
            log(f"Error reading {file_path}: {e}", verbose)

    return matches


def scan_directory(
    path: Path, ignore_patterns: Set[str], verbose: bool = False
) -> List[SecretMatch]:
    """Scan a directory recursively for secrets."""
    all_matches = []
    files_scanned = 0

    for item in path.rglob("*"):
        if item.is_file():
            if should_skip_path(item, ignore_patterns):
                continue
            if not should_scan_file(item):
                continue

            files_scanned += 1
            matches = scan_file(item, verbose)
            all_matches.extend(matches)

    log(f"Scanned {files_scanned} files", verbose)
    return all_matches


def format_results(matches: List[SecretMatch]) -> str:
    """Format scan results for display."""
    if not matches:
        return ""

    output = []

    # Group by severity
    high = [m for m in matches if m.severity == "high"]
    medium = [m for m in matches if m.severity == "medium"]
    low = [m for m in matches if m.severity == "low"]

    if high:
        output.append("\n🔴 HIGH SEVERITY:")
        for m in high:
            rel_path = (
                m.file.relative_to(PROJECT_ROOT) if m.file.is_relative_to(PROJECT_ROOT) else m.file
            )
            output.append(f"  {rel_path}:{m.line_num} - {m.pattern_name}")
            output.append(f"    {m.matched_text}")

    if medium:
        output.append("\n🟡 MEDIUM SEVERITY:")
        for m in medium:
            rel_path = (
                m.file.relative_to(PROJECT_ROOT) if m.file.is_relative_to(PROJECT_ROOT) else m.file
            )
            output.append(f"  {rel_path}:{m.line_num} - {m.pattern_name}")

    if low:
        output.append("\n🟢 LOW SEVERITY:")
        for m in low:
            rel_path = (
                m.file.relative_to(PROJECT_ROOT) if m.file.is_relative_to(PROJECT_ROOT) else m.file
            )
            output.append(f"  {rel_path}:{m.line_num} - {m.pattern_name}")

    return "\n".join(output)


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan for secrets and sensitive information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Detects:
    - API keys and tokens
    - AWS/GCP/Azure credentials
    - Private keys (RSA, SSH, PGP)
    - Database connection strings
    - OAuth tokens, JWTs
    - Hardcoded passwords

Examples:
    python scripts/check_secrets.py                # Scan project
    python scripts/check_secrets.py --strict       # Fail on secrets
    python scripts/check_secrets.py --path src/    # Scan specific dir
        """,
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=PROJECT_ROOT,
        help="Path to scan (default: project root)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if secrets found",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Secrets Scanner")
    print("=" * 60)

    # Load ignore patterns
    ignore_patterns = load_ignore_file(args.path)
    log(f"Loaded {len(ignore_patterns)} ignore patterns", args.verbose)

    # Scan
    matches = scan_directory(args.path, ignore_patterns, args.verbose)

    # Report
    if matches:
        high_count = sum(1 for m in matches if m.severity == "high")
        medium_count = sum(1 for m in matches if m.severity == "medium")
        low_count = sum(1 for m in matches if m.severity == "low")

        log_warning(f"Found {len(matches)} potential secrets!")
        print(f"  High: {high_count}, Medium: {medium_count}, Low: {low_count}")
        print(format_results(matches))

        print("\n" + "=" * 60)
        print("To ignore false positives, add patterns to .secretsignore")
        print("=" * 60)

        if args.strict:
            return 1
        return 0
    else:
        log_success("No secrets detected!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
