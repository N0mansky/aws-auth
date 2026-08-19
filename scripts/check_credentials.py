#!/usr/bin/env python3
"""Pre-commit Credential & Secret Scanner for aws-auth.

Scans staged git changes or repository files for sensitive credentials,
API keys, tokens, and private keys before they can be committed.

Usage:
    python scripts/check_credentials.py [--staged | --all | --files <paths...>]
    python scripts/check_credentials.py --install-hook
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# Secret detection patterns with descriptive labels
SECRET_PATTERNS = [
    (
        "AWS Access Key ID (AKIA/ASIA/ABIA/ACCA)",
        re.compile(r"\b(AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")
    ),
    (
        "AWS Secret Access Key",
        re.compile(r"""(?i)(?:aws_secret_access_key|aws_sec|secret_key)\s*[:=]\s*['"]?([A-Za-z0-9/+=]{40})['"]?""")
    ),
    (
        "AWS Session Token",
        re.compile(r"""(?i)(?:aws_session_token|session_token)\s*[:=]\s*['"]?([A-Za-z0-9/+=]{100,})['"]?""")
    ),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN\s+(?:RSA|OPENSSH|DSA|EC|PGP)?\s*PRIVATE\s+KEY-----")
    ),
    (
        "GitHub Personal Access Token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b|\bgithub_pat_[A-Za-z0-9_]{82}\b")
    ),
    (
        "Slack Token",
        re.compile(r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}\b")
    ),
    (
        "Generic Bearer / API Token",
        re.compile(r"""(?i)(?:bearer\s+[a-zA-Z0-9_\-\.]{32,}|api[_-]?key\s*[:=]\s*['"][a-zA-Z0-9_\-]{24,}['"])""")
    ),
]

# Sensitive file name patterns that should never be tracked
BLOCKED_FILE_PATTERNS = [
    re.compile(r"^.*\.pem$", re.IGNORECASE),
    re.compile(r"^.*\.key$", re.IGNORECASE),
    re.compile(r"^.*\.p12$", re.IGNORECASE),
    re.compile(r"^.*\.pfx$", re.IGNORECASE),
    re.compile(r"^.*sso_access_token\.json$", re.IGNORECASE),
    re.compile(r"^.*cached_token_.*\.json$", re.IGNORECASE),
    re.compile(r"^.*\.env$", re.IGNORECASE),
    re.compile(r"^.*\.env\..*$", re.IGNORECASE),
    re.compile(r"^.*id_rsa(\.pub)?$", re.IGNORECASE),
    re.compile(r"^.*id_ed25519(\.pub)?$", re.IGNORECASE),
]

# Known harmless dummy/placeholder values
KNOWN_SAFE_SUBSTRINGS = [
    "EXAMPLEKEY",
    "AKIAIOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "***masked***",
    "test-secret",
    "placeholder",
    "dummy",
    "00000000000000000000",
    "XXXXXXXXXXXXXXXXXXXX",
]

# Inline directives to ignore a false positive
SUPPRESSION_FLAGS = [
    "pragma: allowlist secret",
    "nosec",
    "noqa: secret-check",
    "skip-secret-check",
]


def is_suppressed(line: str) -> bool:
    """Check if the line contains an explicit suppression directive."""
    lower = line.lower()
    return any(flag.lower() in lower for flag in SUPPRESSION_FLAGS)


def is_known_safe(matched_text: str) -> bool:
    """Check if the matched text is an obvious known dummy/placeholder."""
    for safe in KNOWN_SAFE_SUBSTRINGS:
        if safe in matched_text:
            return True
    return False


def mask_secret(secret: str) -> str:
    """Safely truncate and mask a detected secret for display."""
    if len(secret) <= 8:
        return "****"
    return secret[:4] + "..." + secret[-4:]


def check_file_path(file_path: str) -> Optional[str]:
    """Check if the filename itself is a sensitive file pattern."""
    basename = os.path.basename(file_path)
    for pattern in BLOCKED_FILE_PATTERNS:
        if pattern.search(basename) or pattern.search(file_path):
            # Allow tests that mock these filenames if inside tests directory
            if file_path.startswith("tests/") and not os.path.exists(file_path):
                continue
            return f"Blocked sensitive file name: {file_path}"
    return None


def scan_content(content: str, file_path: str) -> List[Dict[str, Any]]:
    """Scan string content for secrets and return a list of findings."""
    findings = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        if is_suppressed(line):
            continue

        for rule_name, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                matched_str = match.group(0)
                if is_known_safe(matched_str):
                    continue

                # In test files, ignore dummy strings like test-key or mocks
                if file_path.startswith("tests/") and any(
                    x in line.lower() for x in ["mock", "test", "fake", "fixture", "example", "dummy"]
                ):
                    continue

                findings.append({
                    "file": file_path,
                    "line_number": line_num,
                    "rule": rule_name,
                    "snippet": line.strip()[:100],
                    "masked_match": mask_secret(matched_str),
                })
    return findings


def get_staged_files() -> List[str]:
    """Get list of staged files in git."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True
        )
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception as e:
        print(f"⚠️  Error fetching staged files: {e}", file=sys.stderr)
        return []


def get_staged_content(file_path: str) -> str:
    """Get staged diff content for a specific file."""
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--", file_path],
            capture_output=True,
            text=True,
            check=True
        )
        # Extract only added lines (+) from the diff
        added_lines = []
        for line in res.stdout.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
        return "\n".join(added_lines)
    except Exception:
        # Fallback to reading disk file if diff fails
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""


def get_all_tracked_files() -> List[str]:
    """Get all git tracked files in the repo."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True
        )
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception as e:
        print(f"⚠️  Error fetching tracked files: {e}", file=sys.stderr)
        return []


def install_git_hook() -> bool:
    """Install this scanner as a pre-commit git hook."""
    repo_root = Path(__file__).resolve().parent.parent
    hooks_dir = repo_root / ".githooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    hook_content = """#!/bin/sh
# aws-auth credential pre-commit check
python3 scripts/check_credentials.py --staged
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Pre-commit check failed: Secrets or credentials detected."
    echo "   Please remove the secrets or add '# pragma: allowlist secret' if it is a false positive."
    exit 1
fi
exit 0
"""
    hook_path.write_text(hook_content, encoding="utf-8")
    try:
        os.chmod(hook_path, 0o755)
    except Exception:
        pass

    # Configure git core.hooksPath
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo_root, check=False)

    # Also write to .git/hooks/pre-commit for backward compatibility
    git_hooks_dir = repo_root / ".git" / "hooks"
    if git_hooks_dir.exists():
        git_hook_file = git_hooks_dir / "pre-commit"
        git_hook_file.write_text(hook_content, encoding="utf-8")
        try:
            os.chmod(git_hook_file, 0o755)
        except Exception:
            pass

    print("✅ Pre-commit hook successfully installed in .githooks/pre-commit and configured in git!")
    return True


def run_scanner(files_to_check: List[str], is_diff_mode: bool = False) -> int:
    """Run scanner across specified files and report issues."""
    all_findings = []
    blocked_files = []

    for file_path in files_to_check:
        # Ignore binary or non-text extensions
        if any(file_path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe", ".bin", ".pyc"]):
            continue

        # Check filename
        file_issue = check_file_path(file_path)
        if file_issue:
            blocked_files.append(file_issue)

        # Read content
        if is_diff_mode:
            content = get_staged_content(file_path)
        else:
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

        findings = scan_content(content, file_path)
        all_findings.extend(findings)

    # Report results
    if blocked_files or all_findings:
        print("\n" + "=" * 70)
        print("🚨  SECURITY ALERT: Potential Secrets / Credentials Detected!")
        print("=" * 70)

        if blocked_files:
            print("\n🚫 Sensitive Files Blocked from Commit:")
            for issue in blocked_files:
                print(f"   • {issue}")

        if all_findings:
            print("\n🔑 Detected Credentials:")
            for finding in all_findings:
                print(f"\n   📄 File: {finding['file']}:{finding['line_number']}")
                print(f"      Rule: {finding['rule']}")
                print(f"      Match: {finding['masked_match']}")
                print(f"      Code: {finding['snippet']}")

        print("\n" + "─" * 70)
        print("💡 How to fix:")
        print("   1. Remove actual secrets/credentials before committing.")
        print("   2. For legitimate placeholder/test values, add an inline suppression:")
        print("      # pragma: allowlist secret")
        print("=" * 70 + "\n")
        return 1

    print("🛡️  Credential scan passed: No secrets or sensitive files detected.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-commit credential and secret scanner for aws-auth.")
    parser.add_argument("--staged", action="store_true", help="Scan only git staged changes (default)")
    parser.add_argument("--all", action="store_true", help="Scan all tracked files in repository")
    parser.add_argument("--files", nargs="+", help="Scan specific files")
    parser.add_argument("--install-hook", action="store_true", help="Install git pre-commit hook")

    args = parser.parse_args()

    if args.install_hook:
        install_git_hook()
        return 0

    if args.files:
        return run_scanner(args.files, is_diff_mode=False)
    elif args.all:
        files = get_all_tracked_files()
        return run_scanner(files, is_diff_mode=False)
    else:
        # Default: staged
        staged = get_staged_files()
        if not staged:
            print("🛡️  No staged files to scan.")
            return 0
        return run_scanner(staged, is_diff_mode=True)


if __name__ == "__main__":
    sys.exit(main())
