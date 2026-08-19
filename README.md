<div align="center">

# ⚡ AWS-Auth

### Fast, Intelligent AWS SSO Authentication & Model Context Protocol (MCP) Server

[![CI](https://github.com/N0mansky/aws-auth/actions/workflows/ci.yml/badge.svg)](https://github.com/N0mansky/aws-auth/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/N0mansky/aws-auth?color=blue&logo=github)](https://github.com/N0mansky/aws-auth/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Ready](https://img.shields.io/badge/MCP-Server%20Ready-purple.svg)](https://modelcontextprotocol.io/)

**Eliminate AWS SSO login fatigue.** Zero configuration boilerplate, smart role prioritization, atomic credential caching, and native AI pair-programming integration.

[Quick Start](#-quick-start) •
[Why aws-auth?](#-why-aws-auth-vs-alternatives) •
[AI / MCP Integration](#-ai-agent-integration-model-context-protocol) •
[Features](#-key-features) •
[Documentation](#-documentation)

---

</div>

```text
  ┌───────────────────────┐       ┌────────────────────────┐       ┌───────────────────────┐
  │  IAM Identity Center  │ ────> │       aws-auth         │ ────> │  ~/.aws/credentials   │
  │     (AWS SSO OIDC)    │       │  (Smart Role Selector) │       │ (Strict 0600 POSIX)   │
  └───────────────────────┘       └───────────┬────────────┘       └───────────┬───────────┘
                                              │                                │
                                  ┌───────────▼────────────┐       ┌───────────▼───────────┐
                                  │   MCP Server (stdio)   │       │ Terraform / K8s / CLI │
                                  │ (Claude / Cursor / AI) │       │ (Instant Compatibility)│
                                  └────────────────────────┘       └───────────────────────┘
```

---

## 💡 Why `aws-auth` vs Alternatives?

| Feature | `aws-auth` | Official `aws sso login` | `granted` / `assume` | `aws-vault` |
| :--- | :---: | :---: | :---: | :---: |
| **Zero-Config Account Discovery** | ✅ **Automatic** | ❌ Requires manual `~/.aws/config` | ⚠️ Partial | ❌ Manual |
| **Model Context Protocol (MCP)** | ✅ **Native built-in** | ❌ None | ❌ None | ❌ None |
| **1-Second MRU / Pinned Logins** | ✅ **Smart Prioritization** | ❌ None | ⚠️ History prompt | ❌ None |
| **Real-time Substring & Alias Filter** | ✅ **Instant typing** | ❌ None | ✅ Yes | ❌ None |
| **Direct `~/.aws/credentials` Sync** | ✅ **Atomic & `0600`** | ❌ Token cache only | ⚠️ Shell wrapper | ⚠️ Keychain wrapper |
| **Legacy & GUI Tool Compatibility** | ✅ **100% Out of Box** | ⚠️ Many tools fail | ⚠️ Requires wrapper | ⚠️ Requires wrapper |
| **WSL2 -> Windows Browser Bridge** | ✅ **Automatic** | ❌ Fails / manual copy | ⚠️ Partial | ❌ No |
| **EC2 SSM & EKS Context Switching** | ✅ **Built-in** | ❌ Separate tools | ❌ Separate tools | ❌ No |

👉 **Read the full [Feature Comparison Guide](docs/COMPARISON.md)**.

---

## ✨ Key Features

- ⚡ **Zero-Boilerplate Discovery**: No need to maintain hundreds of lines in `~/.aws/config`. Enter your SSO Start URL once, and all authorized accounts and roles are loaded dynamically.
- ⭐ **Smart Role Prioritization (MRU)**: Automatically pins your most recently used roles (e.g. `QA Admin`, `Prod Admin`) to `#1` and `#2`. Pressing `Enter` logs you in within **1 second**.
- 🔍 **Interactive Substring Search**: Type any keyword (`prod`, `qa`, `admin`, `gpu`, `eks`) at the selection prompt to instantly filter dozens of accounts.
- 🤖 **Native Model Context Protocol (MCP) Server**: Expose AWS profile switching, caller identity, and EC2/EKS exploration to LLM pair programmers (Claude Desktop, Cursor, Antigravity, Gemini).
- 🔒 **Enterprise-Grade Security**: Strict POSIX `0600` file permissions, atomic file replacement (`os.replace`), and 300-second expiration safety margins.
- 🌐 **WSL2 Seamless Browser Bridge**: Automatically detects WSL2 and opens authorization URLs directly in your Windows host browser.
- ☸️ **DevOps Acceleration**: Instant EC2 SSM shell sessions and 1-click Amazon EKS kubeconfig context switching.

---

## 📦 Installation

### Option 1: Standalone Binary (Recommended)

Download the latest pre-compiled binary from [GitHub Releases](https://github.com/N0mansky/aws-auth/releases/latest):

#### Windows (PowerShell 1-Liner)
Run in PowerShell to automatically download the binary and configure your PATH:
```powershell
irm https://raw.githubusercontent.com/N0mansky/aws-auth/main/install.ps1 | iex
```

*Or manual download via PowerShell:*
```powershell
curl.exe -L https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-windows-amd64.exe -o aws-auth.exe
```

#### Linux (x86_64)
```bash
curl -L https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-linux-amd64 -o aws-auth
chmod +x aws-auth && sudo mv aws-auth /usr/local/bin/
```

#### macOS (Universal)
```bash
curl -L https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-macos-universal -o aws-auth
chmod +x aws-auth && sudo mv aws-auth /usr/local/bin/
```

### Option 2: Install via pip

```bash
pip install git+https://github.com/N0mansky/aws-auth.git
```

### Option 3: Clone & Install from Source

```bash
git clone https://github.com/N0mansky/aws-auth.git
cd aws-auth

./install.sh                      # Linux / macOS / WSL2
powershell .\install.ps1          # Windows (PowerShell)
.\install.bat                     # Windows (Command Prompt)
```

---

## 🚀 Quick Start

### 1. Interactive Login

```bash
aws-auth
```

```text
Available account-role combinations (Showing 1-10 of 18):
+-----+------------------------------+-----------------+------------------------------+-------------+
| #   | Account                      | Account ID      | Role                         | Region      |
+-----+------------------------------+-----------------+------------------------------+-------------+
| 1   | ⭐ Production-App (PROD)        | (111222333444)  | AdministratorAccess     | us-east-1   |
| 2   | ⭐ Staging-Web (QA)          | (555666777888)  | AdministratorAccess     | us-east-1   |
| 3   | Analytics-Data                  | (999888777666)  | AdministratorAccess     | us-east-1   |
...
Select number 1-10 (default: 1) (type keyword to filter): [ENTER]

✅ Profile 'production-app-admin' set as default in ~/.aws/credentials.
```

### 2. Configure Portal & Custom Aliases

```bash
aws-auth --configure
```

Customize environment labels and preferred accounts in `~/.aws-auth/config.json`:
```json
{
  "sso_start_url": "https://my-company.awsapps.com/start",
  "sso_region": "us-east-1",
  "preferred_accounts": ["Staging-Web", "Production-App"],
  "aliases": {
    "555666777888": "QA",
    "111222333444": "PROD"
  }
}
```

---

## 🤖 AI Agent Integration (Model Context Protocol)

`aws-auth` runs as a high-performance **MCP Server** over stdio.

### Add to Claude Desktop (`claude_desktop_config.json`) or Cursor:

```json
{
  "mcpServers": {
    "aws-auth": {
      "command": "aws-auth",
      "args": ["--mcp"]
    }
  }
}
```

### What AI Assistants Can Do with `aws-auth`:
- Check active AWS Account, Region, and IAM Role ARN (`aws_get_caller_identity`).
- Switch active AWS profile (`aws_switch_profile`) without human intervention.
- Inspect running EC2 instances and Amazon EKS clusters (`aws_list_ec2_instances`, `aws_list_eks_clusters`).
- Update local Kubernetes context (`aws_update_kubeconfig`).

👉 **Read the full [MCP Setup & Tool Reference Guide](docs/MCP_GUIDE.md)**.

---

## 🛠️ CLI Command Reference

```bash
# Core Authentication
aws-auth                     # Interactive SSO login & smart role switch
aws-auth --configure         # Interactive SSO portal setup
aws-auth --identity          # Show current STS caller identity
aws-auth --refresh-cache     # Force refresh remote account/role metadata

# Profile Management
aws-auth --list-profiles     # List all stored AWS profiles
aws-auth --switch-profile    # Switch active default profile
aws-auth --set-default NAME  # Set specific profile as default
aws-auth --delete NAME       # Delete profile credentials

# Resource Discovery & DevOps
aws-auth --list-ec2          # List EC2 instances and connect via SSM
aws-auth --list-eks          # List EKS clusters and update kubeconfig

# Scripting & Headless Automation
aws-auth --list-profiles --json
aws-auth --identity --json
eval $(aws-auth --export-env prod-profile)  # Export AWS keys to current shell

# AWS credential_process standard
aws-auth --credential-process my-profile
```

---

## 📚 Documentation

- 📊 [Comparison with AWS CLI, Granted & AWS-Vault](docs/COMPARISON.md)
- 🤖 [Model Context Protocol (MCP) Guide](docs/MCP_GUIDE.md)
- 🐧 [WSL2 Setup & Windows Integration Guide](docs/WSL2_SETUP.md)
- 💻 [Linux Detailed Installation](docs/aws-kubectl-linux-install.md)
- 🪟 [Windows Detailed Installation](docs/aws-kubectl-windows-install.md)

---

## 🤝 Contributing

Contributions are welcome! Please check out [CONTRIBUTING.md](CONTRIBUTING.md) for details on setting up a development environment and running tests.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
