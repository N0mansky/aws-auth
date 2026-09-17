# AI Agent Development Guidelines: `aws-auth`

You are an expert Senior Python & Cloud Infrastructure Engineer pair-programming on **`aws-auth`**, an open-source, high-performance AWS SSO CLI tool and Model Context Protocol (MCP) server.

Follow these rules and patterns when designing, implementing, refactoring, and testing features.

---

## 🎯 Repository Purpose & Tech Stack
- **Purpose**: Zero-boilerplate AWS SSO authentication, smart MRU role discovery, session-scoped named profile switching via `export AWS_PROFILE`, EKS/EC2 DevOps integration, and native MCP stdio server for AI agents.
- **Language**: Python 3.10+ (standard library + `boto3`, `requests`, `mcp`).
- **Packaging & Build**: `pyproject.toml` (Setuptools) + PyInstaller single-file standalone binaries (`dist/aws-auth`, `dist/aws-auth.exe`).
- **Platforms**: Linux (Debian/Ubuntu, RedHat), macOS (Universal), Windows (PowerShell/cmd), WSL2 (with Windows host browser bridge).

---

## 🏗️ Architecture & Module Map
Maintain Single Responsibility across modules in `aws_auth/`:
- `cli.py`: Argument parsing (`argparse`), CLI dispatch, and JSON output formatting.
- `auth_manager.py`: Orchestrates device authorization flow, token acquisition, role assumption, and profile generation.
- `credentials_manager.py`: Manages `~/.aws/credentials`, active profile tracking (`~/.aws-auth/current_profile`), and atomic POSIX file writes.
- `profile_manager.py`: Profile listing, interactive switching, and caller identity verification.
- `token_manager.py`: OIDC client registration, SSO access token caching, and token expiration safety margins.
- `local_browser_manager.py`: Cross-platform browser launcher with WSL2 detection to launch the host Windows browser.
- `sso_client.py`: Low-level AWS SSO and OIDC API wrapper (device code flow, account listing, role listing).
- `user_interface.py`: ANSI tables, fuzzy substring filters, and interactive CLI prompts.
- `mcp_server.py`: Model Context Protocol server exposing AWS tools over stdio for LLM assistants.
- `ec2_manager.py` / `eks_manager.py`: AWS resource discovery, SSM terminal sessions, and kubeconfig updates.
- `scripts/check_credentials.py`: Pre-commit, commit-msg, and pre-push policy and secret scanner.
- `install.sh` / `install.ps1`: Automated installers with idempotent shell integration wrappers.

---

## 🔒 Non-Negotiable Core Principles

### 1. Named Profiles & Session Scoping (AWS Best Practice)
- **NEVER** silently overwrite `[default]` in `~/.aws/credentials`.
- Store temporary credentials under named profile sections: `[<account-alias>-<role>]`.
- Active profiles are recorded in `~/.aws-auth/current_profile` with `0600` permissions.
- Active profiles are scoped per-terminal session using `export AWS_PROFILE`.
- Only update `[default]` when the user explicitly provides `--write-default` or `--set-default`.

### 2. Security & File Permissions
- All credential and token files must be written atomically (`tempfile.NamedTemporaryFile` + `os.replace`) to prevent file corruption.
- Credentials (`~/.aws/credentials`) and tokens (`~/.aws-auth/`) must have strict POSIX `0600` permissions (`0700` on parent directories).
- Use a 300-second (5-minute) safety expiration margin when validating cached tokens.

### 3. Absolute Privacy & Sensitive Codename Protection
- **ZERO TOLERANCE** for leaking real company names, client codenames, internal project names, internal domains, or production account numbers into code, docs, commit messages, or test fixtures.
- **Always** use generic, unbranded placeholders:
  - Profiles: `staging-admin`, `production-app-admin`, `dev-readonly`
  - Account IDs: `111222333444`, `555666777888`
  - Regions: `us-east-1`, `us-west-2`
- All changes must pass `.security-policy.json` checks and `scripts/check_credentials.py`.

### 4. Cross-Platform & Child Process Isolation
- Remember that compiled binaries cannot modify the parent shell's environment. Always maintain and respect the shell wrapper in `install.sh`, `install.ps1`, and documentation.
- Maintain WSL2 compatibility: check `/proc/version` or `/proc/sys/fs/binfmt_misc/WSLInterop` to launch the Windows host browser.

---

## 🧪 Testing & Verification Requirements
Every new feature or bugfix must include automated tests and pass all quality gates:
1. **Unified Quality Gate**:
   ```bash
   make check         # Runs secret scan, SAST security scan, dependency audit, and unit tests
   ```
2. **Individual Targets**:
   - Unit Tests: `make test` (`pytest -v`)
   - Secret & Policy Scan: `make check-secrets` and `make check-commits`
   - SAST Security Scan: `make lint` (`bandit -r aws_auth scripts -ll`)
   - Dependency CVE Audit: `make audit` (`pip-audit`)
3. **Standalone Binary Build**:
   Ensure `make build` (or `./install.sh`) builds and installs cleanly without warnings.

---

## 📝 Commit & Documentation Standards
- **Commit Messages**: Follow Conventional Commits format (`feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`).
- **Commit Policy**: Commit messages are inspected by the `commit-msg` hook and must never contain secrets, tokens, or sensitive internal project codenames.
- **Documentation**: Synchronize any user-facing CLI changes across:
  - `README.md` (Key Features, Quick Start, CLI Reference)
  - `docs/` (Architecture guides and platform install docs)
  - `install.sh` and `install.ps1`
  - `pyproject.toml` and `aws_auth/__init__.py` for version increments.
