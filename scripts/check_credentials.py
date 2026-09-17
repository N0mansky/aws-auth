#!/usr/bin/env python3
"""Pre-commit Credential, Secret & Policy Scanner for aws-auth.

Scans staged git changes, commit messages, and repository files for:
1. Sensitive credentials, API keys, tokens, and private keys.
2. Blocked internal project names/codenames configured in .security-policy.json.
3. Forbidden sensitive file patterns.

Usage:
    python scripts/check_credentials.py [--staged | --all | --files <paths...>]
    python scripts/check_credentials.py --commit-msg <path_to_commit_msg_file>
    python scripts/check_credentials.py --check-commits [N]
    python scripts/check_credentials.py --install-hook
"""

import argparse
import json
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

# Default fallback blocked project terms if policy file is absent
DEFAULT_BLOCKED_TERMS = [
    {
        "name": "Internal Project / Account Codename",
        "pattern": r"(?i)\b(?:confidential|internal|secret|proprietary)-(?:release|admin|prod|staging|dev)\b",
        "description": "Internal project codenames and infrastructure identifiers are not permitted in open-source repository"
    }
]


def load_security_policy() -> Dict[str, Any]:
    """Load security policy configuration in order of privacy precedence:
    1. Local user private directory: ~/.aws-auth/security-policy.json (never tracked in git)
    2. Local workspace override: .security-policy.local.json or .security-policy.json (gitignored)
    3. Repository template: .security-policy.example.json
    """
    repo_root = Path(__file__).resolve().parent.parent

    # Candidate locations in priority order
    candidate_paths = [
        Path(os.path.expanduser("~/.aws-auth/security-policy.json")),
        repo_root / ".security-policy.local.json",
        repo_root / ".security-policy.json",
        repo_root / ".security-policy.example.json",
    ]

    policy_data: Dict[str, Any] = {}
    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    policy_data = json.load(f)
                    break
            except Exception as e:
                print(f"⚠️  Error loading {path}: {e}", file=sys.stderr)

    # Allow injecting custom blocked terms via environment variable (e.g. in CI or local shell)
    env_terms = os.environ.get("AWS_AUTH_BLOCKED_TERMS")
    if env_terms:
        if "blocked_terms" not in policy_data:
            policy_data["blocked_terms"] = list(DEFAULT_BLOCKED_TERMS)
        for term_pat in env_terms.split(","):
            term_pat = term_pat.strip()
            if term_pat:
                policy_data["blocked_terms"].append({
                    "name": "Environment-Defined Blocked Term",
                    "pattern": term_pat,
                    "description": "Blocked via AWS_AUTH_BLOCKED_TERMS environment variable"
                })

    return policy_data


def get_blocked_terms() -> List[Tuple[str, Any]]:
    """Retrieve compiled regex patterns for blocked sensitive terms/codenames."""
    policy = load_security_policy()
    terms = policy.get("blocked_terms", DEFAULT_BLOCKED_TERMS)
    compiled = []
    for item in terms:
        name = item.get("name", "Sensitive Term")
        pat_str = item.get("pattern", "")
        if pat_str:
            try:
                compiled.append((name, re.compile(pat_str)))
            except re.error as e:
                print(f"⚠️  Invalid regex in security policy ({name}): {e}", file=sys.stderr)
    return compiled


def get_blocked_commit_terms() -> List[Tuple[str, Any]]:
    """Retrieve compiled regex patterns for commit message checks."""
    policy = load_security_policy()
    terms = policy.get("blocked_commit_terms", DEFAULT_BLOCKED_TERMS)
    compiled = []
    for item in terms:
        name = item.get("name", "Sensitive Commit Term")
        pat_str = item.get("pattern", "")
        if pat_str:
            try:
                compiled.append((name, re.compile(pat_str)))
            except re.error as e:
                print(f"⚠️  Invalid commit regex in security policy ({name}): {e}", file=sys.stderr)
    return compiled


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

    # Check hardcoded patterns
    patterns_to_check = list(BLOCKED_FILE_PATTERNS)

    # Add custom blocked files from policy if defined
    policy = load_security_policy()
    for custom_pat in policy.get("blocked_files", []):
        try:
            patterns_to_check.append(re.compile(custom_pat, re.IGNORECASE))
        except re.error:
            pass

    for pattern in patterns_to_check:
        if pattern.search(basename) or pattern.search(file_path):
            # Allow tests that mock these filenames if inside tests directory
            if file_path.startswith("tests/") and not os.path.exists(file_path):
                continue
            return f"Blocked sensitive file name: {file_path}"
    return None


def scan_content(content: str, file_path: str) -> List[Dict[str, Any]]:
    """Scan string content for secrets and policy-blocked terms."""
    findings = []
    lines = content.splitlines()
    blocked_terms = get_blocked_terms()

    for line_num, line in enumerate(lines, start=1):
        if is_suppressed(line):
            continue

        # 1. Check Secret Patterns
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

        # 2. Check Blocked Sensitive Terms / Project Policy Patterns
        # (Exclude policy definition files and test files testing the scanner itself)
        if not (file_path.endswith(".security-policy.json") or file_path.endswith("test_check_credentials.py") or file_path.endswith("check_credentials.py")):
            for rule_name, pattern in blocked_terms:
                for match in pattern.finditer(line):
                    matched_str = match.group(0)
                    findings.append({
                        "file": file_path,
                        "line_number": line_num,
                        "rule": f"Sensitive Policy Violation: {rule_name}",
                        "snippet": line.strip()[:100],
                        "masked_match": mask_secret(matched_str),
                    })

    return findings


def scan_commit_message(message: str) -> List[Dict[str, Any]]:
    """Scan commit message text for secrets and sensitive project codenames."""
    findings = []
    lines = message.splitlines()
    commit_terms = get_blocked_commit_terms()

    for line_num, line in enumerate(lines, start=1):
        # Ignore git comments starting with #
        if line.strip().startswith("#"):
            continue

        if is_suppressed(line):
            continue

        # 1. Check Secret Patterns
        for rule_name, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                matched_str = match.group(0)
                if is_known_safe(matched_str):
                    continue
                findings.append({
                    "file": "COMMIT_MSG",
                    "line_number": line_num,
                    "rule": rule_name,
                    "snippet": line.strip()[:100],
                    "masked_match": mask_secret(matched_str),
                })

        # 2. Check Blocked Commit Terms
        for rule_name, pattern in commit_terms:
            for match in pattern.finditer(line):
                matched_str = match.group(0)
                findings.append({
                    "file": "COMMIT_MSG",
                    "line_number": line_num,
                    "rule": f"Sensitive Commit Policy Violation: {rule_name}",
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
    """Install pre-commit, commit-msg, and pre-push git hooks."""
    repo_root = Path(__file__).resolve().parent.parent
    hooks_dir = repo_root / ".githooks"
    hooks_dir.mkdir(exist_ok=True)

    # 1. pre-commit hook
    pre_commit_path = hooks_dir / "pre-commit"
    pre_commit_content = """#!/bin/sh
# aws-auth credential & policy pre-commit check
python3 scripts/check_credentials.py --staged
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Pre-commit check failed: Secrets or sensitive policy violations detected."
    echo "   Please review findings and resolve them before committing."
    exit 1
fi
exit 0
"""
    pre_commit_path.write_text(pre_commit_content, encoding="utf-8")
    try:
        os.chmod(pre_commit_path, 0o755)  # nosec B103
    except Exception:
        pass

    # 2. commit-msg hook
    commit_msg_path = hooks_dir / "commit-msg"
    commit_msg_content = """#!/bin/sh
# aws-auth commit message policy check
python3 scripts/check_credentials.py --commit-msg "$1"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Commit-msg check failed: Commit message contains sensitive terms or credentials."
    exit 1
fi
exit 0
"""
    commit_msg_path.write_text(commit_msg_content, encoding="utf-8")
    try:
        os.chmod(commit_msg_path, 0o755)  # nosec B103
    except Exception:
        pass

    # 3. pre-push hook
    pre_push_path = hooks_dir / "pre-push"
    pre_push_content = """#!/bin/sh
# aws-auth pre-push repository & policy scan
python3 scripts/check_credentials.py --all
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Pre-push check failed: Secrets or sensitive policy violations detected in tracked files."
    exit 1
fi
exit 0
"""
    pre_push_path.write_text(pre_push_content, encoding="utf-8")
    try:
        os.chmod(pre_push_path, 0o755)  # nosec B103
    except Exception:
        pass

    # Configure git core.hooksPath
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo_root, check=False)

    # Also write to .git/hooks for backward compatibility
    git_hooks_dir = repo_root / ".git" / "hooks"
    if git_hooks_dir.exists():
        for name, content in [
            ("pre-commit", pre_commit_content),
            ("commit-msg", commit_msg_content),
            ("pre-push", pre_push_content),
        ]:
            target = git_hooks_dir / name
            target.write_text(content, encoding="utf-8")
            try:
                os.chmod(target, 0o755)  # nosec B103
            except Exception:
                pass

    print("✅ Git hooks (pre-commit, commit-msg, pre-push) successfully installed in .githooks and configured in git!")
    return True


def run_commit_msg_scanner(commit_msg_file: str) -> int:
    """Run check on a commit message file."""
    if not os.path.exists(commit_msg_file):
        print(f"⚠️  Commit message file not found: {commit_msg_file}", file=sys.stderr)
        return 1

    with open(commit_msg_file, "r", encoding="utf-8", errors="ignore") as f:
        message = f.read()

    findings = scan_commit_message(message)
    if findings:
        print("\n" + "=" * 70)
        print("🚨  SECURITY ALERT: Commit Message Contains Sensitive Data or Policy Violation!")
        print("=" * 70)
        for finding in findings:
            print(f"\n   📄 Location: Line {finding['line_number']}")
            print(f"      Rule: {finding['rule']}")
            print(f"      Match: {finding['masked_match']}")
            print(f"      Text: {finding['snippet']}")
        print("\n" + "─" * 70)
        print("💡 How to fix:")
        print("   Remove internal project names, codenames, or credentials from your commit message.")
        print("=" * 70 + "\n")
        return 1

    print("🛡️  Commit message scan passed: No sensitive terms or secrets detected.")
    return 0


def run_commits_history_scanner(count: int = 5) -> int:
    """Scan recent commit messages and diffs in HEAD."""
    try:
        res = subprocess.run(
            ["git", "log", f"-n{count}", "--format=COMMIT:%H%n%B%nDIFF:"],
            capture_output=True,
            text=True,
            check=True
        )
    except Exception as e:
        print(f"⚠️  Error reading git log: {e}", file=sys.stderr)
        return 1

    raw_commits = res.stdout.split("COMMIT:")
    has_violations = False

    for c in raw_commits:
        if not c.strip():
            continue
        parts = c.split("DIFF:")
        header_and_msg = parts[0]
        commit_hash = header_and_msg.splitlines()[0].strip() if header_and_msg.splitlines() else "UNKNOWN"
        msg = "\n".join(header_and_msg.splitlines()[1:])

        findings = scan_commit_message(msg)
        if findings:
            has_violations = True
            print(f"\n🚨 Sensitive data in commit {commit_hash[:10]}:")
            for f in findings:
                print(f"   • {f['rule']}: {f['snippet']}")

    if has_violations:
        return 1

    print(f"🛡️  Last {count} commits verified: No sensitive terms or secrets in commit log.")
    return 0


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
        print("🚨  SECURITY ALERT: Potential Secrets or Policy Violations Detected!")
        print("=" * 70)

        if blocked_files:
            print("\n🚫 Sensitive Files Blocked from Commit:")
            for issue in blocked_files:
                print(f"   • {issue}")

        if all_findings:
            print("\n🔑 Detected Violations:")
            for finding in all_findings:
                print(f"\n   📄 File: {finding['file']}:{finding['line_number']}")
                print(f"      Rule: {finding['rule']}")
                print(f"      Match: {finding['masked_match']}")
                print(f"      Code: {finding['snippet']}")

        print("\n" + "─" * 70)
        print("💡 How to fix:")
        print("   1. Remove actual secrets or forbidden project names before committing.")
        print("   2. For legitimate placeholder/test values, add an inline suppression:")
        print("      # pragma: allowlist secret")
        print("   3. Configure custom policies in .security-policy.json if necessary.")
        print("=" * 70 + "\n")
        return 1

    print("🛡️  Security policy & credential scan passed: No secrets or policy violations detected.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-commit credential, secret, and policy scanner for aws-auth.")
    parser.add_argument("--staged", action="store_true", help="Scan only git staged changes (default)")
    parser.add_argument("--all", action="store_true", help="Scan all tracked files in repository")
    parser.add_argument("--files", nargs="+", help="Scan specific files")
    parser.add_argument("--commit-msg", help="Scan a git commit message file")
    parser.add_argument("--check-commits", type=int, nargs="?", const=5, help="Scan the last N commit messages in history")
    parser.add_argument("--install-hook", action="store_true", help="Install git pre-commit, commit-msg, and pre-push hooks")

    args = parser.parse_args()

    if args.install_hook:
        install_git_hook()
        return 0

    if args.commit_msg:
        return run_commit_msg_scanner(args.commit_msg)

    if args.check_commits is not None:
        return run_commits_history_scanner(args.check_commits)

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
