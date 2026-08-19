# AWS SSO Authentication Tool (`aws-auth`)

A modular Python command-line tool for automating AWS SSO (Single Sign-On) authentication, credential caching, and AWS profile management with built-in EC2 and EKS integration.

## Features

- 🔐 **Automated SSO Login**: Fast interactive SSO authentication opening in your default system browser (including native Windows browser launch from WSL2).
- 🎯 **Account & Role Selection**: Interactive selection of AWS accounts and IAM roles.
- 💾 **Credential Caching**: Caches SSO tokens securely in `~/.aws-auth/` to avoid unnecessary logins.
- 🚀 **AWS Profile Management**: Automatically updates AWS credentials file (`~/.aws/credentials`) and allows quick profile switching.
- 💻 **EC2 & EKS Integration**:
  - Direct connection to EC2 instances via AWS SSM Session Manager.
  - Quick cluster discovery and kubeconfig configuration for Amazon EKS.
- 📦 **Multiple Installation Modes**: Standalone executable (via PyInstaller) or standard Python package installation (`pip`).

---

## Prerequisites

- **Python 3.8+**
- **AWS CLI v2** (installed automatically by `install.sh` / `install.bat` if missing)
- **AWS SSM Session Manager Plugin** (optional, for SSM terminal access to EC2)
- **kubectl** (optional, for EKS management)

---

## Installation

### Option 1: Binary Build & Install (Recommended for CLI use)

```bash
# Clone the repository
git clone <repository-url>
cd aws-auth

# Run the installation script
chmod +x install.sh
./install.sh
```

On Windows:
```cmd
install.bat
```

### Option 2: Pip / Virtual Environment

```bash
# Install in editable mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

---

## Usage

### 1. Interactive Authentication & Smart Selection (Default)

```bash
aws-auth
# or: python -m aws_auth
```

- **⭐ Recent First (MRU)**: Automatically pins your most recently used accounts/roles to the top (`#1`, `#2`).
- **⚡ Instant Enter**: Pressing `Enter` automatically selects the `#1` default option.
- **🔍 Substring Filter**: Type any keyword (e.g. `qa`, `prod`, `release`, `gpu`, `admin`) to instantly filter the list. Type `r` to reset.
- **🏷️ Account Aliases & Pinned Accounts**: Customize aliases in `~/.aws-auth/config.json`:
  ```json
  {
    "preferred_accounts": ["Production", "Staging"],
    "aliases": {
      "123456789012": "PROD",
      "987654321098": "QA"
    }
  }
  ```

### 2. Configuration Setup

```bash
# Configure or update your SSO Start URL and Region
aws-auth --configure
```

### 3. Profile Management

```bash
# Interactive profile management menu
aws-auth --manage

# List existing profiles
aws-auth --list-profiles

# Switch active default profile
aws-auth --switch-profile

# Set a specific profile as default
aws-auth --set-default my-profile

# Delete a profile
aws-auth --delete old-profile
```

### 4. EC2 Management & SSM Connection

```bash
# Authenticate and list EC2 instances (connect directly via SSM)
aws-auth --list-ec2

# List EC2 instances in a specific region
aws-auth --list-ec2 --region us-west-2

# Use existing credentials without re-authenticating
aws-auth --list-ec2 --no-auth
```

### 5. EKS Cluster Configuration

```bash
# Authenticate and configure EKS clusters
aws-auth --list-eks

# Configure EKS in specific region without re-auth
aws-auth --list-eks qa-profile --no-auth --region us-west-2
```

---

## 🤖 AI Agent & MCP (Model Context Protocol) Integration

`aws-auth` includes a first-class **Model Context Protocol (MCP)** server that allows AI agents (e.g. Claude Desktop, Antigravity IDE, Cursor, Claude Code) to inspect AWS profiles, switch accounts, check credential validity, export session environment variables, and inspect EC2/EKS resources.

### 1. Launch MCP Server

Run directly with CLI or Python:
```bash
aws-auth --mcp
# or: aws-auth-mcp
# or: python -m aws_auth.mcp_server
```

### 2. Configure MCP Client

Add `aws-auth` to your IDE or client MCP configuration file (e.g. `~/.gemini/config/mcp_config.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aws-auth": {
      "command": "/path/to/aws-auth/venv/bin/python",
      "args": ["-m", "aws_auth.mcp_server"],
      "cwd": "/path/to/aws-auth"
    }
  }
}
```

### 3. Available MCP Tools for AI Agents

| MCP Tool | Description |
| :--- | :--- |
| `aws_list_profiles` | Lists all local AWS profiles, current default profile, and regions. |
| `aws_switch_profile` | Sets target profile as default in `~/.aws/credentials` and returns identity. |
| `aws_get_caller_identity` | Retrieves current AWS Account ID, ARN, and UserId via STS. |
| `aws_ensure_credentials` | Checks credential validity; automatically refreshes token in background if expired. |
| `aws_get_session_env` | Returns unmasked temporary `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` for subprocesses. |
| `aws_list_ec2_instances` | Returns structured JSON list of EC2 instances with state, tags, and IPs. |
| `aws_list_eks_clusters` | Lists EKS clusters in a region with optional kubeconfig configuration. |
| `aws_update_kubeconfig` | Configures local kubeconfig context for an active cluster. |

---

## 💻 Headless & Scripting Usage

For shell scripts and non-interactive CI/CD or agent pipelines:

```bash
# Output JSON format
aws-auth --list-profiles --json
aws-auth --identity --json
aws-auth --set-default dev-profile --json
aws-auth --list-ec2 --no-auth --json
aws-auth --list-eks --no-auth --json

# Export credentials directly to current shell
eval $(aws-auth --export-env dev-profile)
aws s3 ls
```

### AWS `credential_process` Integration

You can configure AWS CLI, Boto3, or Terraform to automatically source credentials via `aws-auth`:

In `~/.aws/config`:
```ini
[profile my-dev-profile]
credential_process = aws-auth --credential-process my-dev-profile
```

---

## Project Structure

```
aws-auth/
├── pyproject.toml              # Standard Python package configuration
├── requirements.txt            # Core runtime dependencies
├── requirements-dev.txt        # Development and build dependencies
├── aws-auth.py                 # Script launcher
├── install.sh                  # Linux/macOS setup and build script
├── install.bat                 # Windows setup and build script
├── aws_auth/                   # Core Python package
│   ├── __init__.py
│   ├── __main__.py             # Enables `python -m aws_auth`
│   ├── cli.py                  # Command-line interface & argument parser
│   ├── auth_manager.py         # SSO authentication orchestrator
│   ├── caller_identity.py      # STS caller identity helper
│   ├── config.py               # Centralized configuration
│   ├── credentials_manager.py  # ~/.aws/credentials file management
│   ├── ec2_manager.py          # EC2 listing and SSM terminal connections
│   ├── eks_manager.py          # EKS cluster discovery and kubeconfig setup
│   ├── local_browser_manager.py# System & WSL2 browser launcher
│   ├── profile_manager.py      # AWS profile switcher and manager
│   ├── sso_client.py           # AWS SSO OIDC client interactions
│   ├── token_manager.py        # Token caching and lifecycle management
│   └── user_interface.py       # Rich terminal UI & prompts
├── docs/                       # Additional setup & architecture docs
└── tests/                      # Unit tests
```

---

## Development & Testing

Run unit tests:
```bash
python3 -m unittest discover tests
```

Build standalone executable locally:
```bash
pyinstaller aws-auth.spec
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
