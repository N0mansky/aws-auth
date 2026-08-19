# Model Context Protocol (MCP) Integration Guide

`aws-auth` comes with a built-in **Model Context Protocol (MCP)** server, enabling AI pair-programmers and LLM agents (such as Claude Desktop, Cursor, Antigravity, and Gemini) to securely inspect AWS infrastructure and switch profiles on your behalf.

---

## 🛠️ Setting Up MCP

### 1. Claude Desktop

Add the following to your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

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

If installed in a virtual environment:
```json
{
  "mcpServers": {
    "aws-auth": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "aws_auth.mcp_server"]
    }
  }
}
```

---

### 2. Cursor / Antigravity IDE

Add to your MCP settings or workspace configuration:

```json
{
  "mcpServers": {
    "aws-auth": {
      "command": "aws-auth-mcp"
    }
  }
}
```

---

## 🧰 Available MCP Tools

| Tool Name | Parameters | Purpose |
| :--- | :--- | :--- |
| `aws_list_profiles` | None | Lists all configured AWS profiles in `~/.aws/credentials` and indicates the default. |
| `aws_switch_profile` | `profile_name` (string) | Changes active default profile in `~/.aws/credentials` instantly without re-authenticating. |
| `aws_get_caller_identity` | `profile_name` (optional) | Returns active AWS Account ID, IAM User/Role ARN, and UserId. |
| `aws_ensure_credentials` | `profile_name` (optional) | Checks if credentials are valid or prompts for browser authentication if expired. |
| `aws_get_session_env` | `profile_name` (optional) | Provides unmasked temporary AWS STS environment variables for isolated command execution. |
| `aws_list_ec2_instances` | `profile_name`, `region` | Lists EC2 instances (ID, State, Public/Private IPs, Name tags). |
| `aws_list_eks_clusters` | `profile_name`, `region` | Lists available Amazon EKS cluster names in the active region. |
| `aws_update_kubeconfig` | `cluster_name`, `region`, `profile_name` | Automatically executes `aws eks update-kubeconfig` to configure local `~/.kube/config`. |

---

## 🔒 Security Guarantee

- **No Hardcoded Secrets**: The MCP server never exposes root AWS secrets or persistent IAM credentials.
- **Strict File Permissions**: All cached tokens and credentials written to disk are enforced with POSIX `0600` permissions.
- **Short-Lived STS Sessions**: Credentials automatically expire based on IAM session policies.
