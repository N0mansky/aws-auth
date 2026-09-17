# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.2.x   | :white_check_mark: |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |

## Automated Security & Policy Scanning

`aws-auth` includes automated security and sensitive data protection checks:

- **Secret & Credential Scanning**: Scans for AWS access keys, session tokens, private keys, bearer tokens, and GitHub PATs.
- **Project Codename & Term Policy**: Enforces `.security-policy.json` to prevent internal project names, client identifiers, or proprietary codenames from being committed to the public repository.
- **Commit Message Policy**: Inspects git commit messages via the `commit-msg` hook to prevent sensitive term leakage in git commit logs.
- **Pre-Push Verification**: Validates the entire repository before pushing changes to remote.

Install the git hooks locally:
```bash
python scripts/check_credentials.py --install-hook
```

Run manual checks:
```bash
python scripts/check_credentials.py --all           # Scan all files
python scripts/check_credentials.py --check-commits # Scan recent commits
```

## Reporting a Vulnerability

If you discover a potential security vulnerability in `aws-auth`, please do **not** open a public GitHub issue.

Please report vulnerabilities privately via [GitHub Security Advisories](https://github.com/N0mansky/aws-auth/security/advisories/new) or by reaching out directly to the repository maintainer.
