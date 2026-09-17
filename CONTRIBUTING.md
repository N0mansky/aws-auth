# Contributing to `aws-auth`

Thank you for your interest in contributing to `aws-auth`!

## Quickstart with `make`

The repository includes a [Makefile](Makefile) that automates setup, testing, linting, security scanning, and builds:

```bash
# 1. View all available targets
make help

# 2. Setup virtual environment, dependencies, and git hooks
make venv
source venv/bin/activate

# 3. Run all unit tests
make test

# 4. Run full security, lint, audit, and test suite
make check

# 5. Build standalone single-file binary
make build
```

---

## Manual Setup

If you prefer setting up manually without `make`:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/aws-auth.git
   cd aws-auth
   ```
2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies and development hooks**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   python scripts/check_credentials.py --install-hook
   ```

---

## Quality & Security Verification

All contributions must pass automated security and quality gates:

| Task | Make Command | Manual Command |
| :--- | :--- | :--- |
| **All Checks** | `make check` | Run all commands below |
| **Unit Tests** | `make test` | `pytest -v` |
| **Secret Scan** | `make check-secrets` | `python scripts/check_credentials.py --all` |
| **Commit Log Scan** | `make check-commits` | `python scripts/check_credentials.py --check-commits 5` |
| **SAST Security** | `make lint` | `bandit -r aws_auth scripts -ll` |
| **CVE Audit** | `make audit` | `pip-audit -r requirements.txt -r requirements-dev.txt --desc on` |
| **Clean Artifacts**| `make clean` | `rm -rf build/ dist/ .pytest_cache` |

For legitimate test fixtures or mock strings, add `# pragma: allowlist secret` at the end of the line.

---

## Pull Request Guidelines

- Create a feature branch (`git checkout -b feat/amazing-feature`).
- Ensure `make check` passes completely without warnings or failures.
- Write unit tests for new features or bug fixes in `tests/`.
- Never include sensitive internal company names, real account numbers, or credentials in code, tests, or commit messages.
- Follow Conventional Commits format (`feat(...)`, `fix(...)`, `docs(...)`).
