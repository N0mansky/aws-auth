# Feature Comparison: `aws-auth` vs Existing Tools

When managing multi-account AWS environments with IAM Identity Center (SSO), developers and DevOps engineers often struggle with repetitive logins, manual `~/.aws/config` boilerplate, tool incompatibilities, and lack of AI-tooling support.

Here is how `aws-auth` compares to alternative solutions:

| Feature / Capability | `aws-auth` | Official `aws sso login` | `granted` / `assume` | `aws-vault` |
| :--- | :---: | :---: | :---: | :---: |
| **Zero-Config Account Discovery** | ✅ **Automatic** | ❌ Manual `~/.aws/config` per account/role | ⚠️ Partial | ❌ Manual setup |
| **Model Context Protocol (MCP) Server** | ✅ **Native built-in** | ❌ None | ❌ None | ❌ None |
| **1-Second MRU / Pinned Role Login** | ✅ **Smart Prioritization** | ❌ None | ⚠️ History prompt | ❌ None |
| **Real-time Substring & Alias Filtering** | ✅ **Instant typing** | ❌ None | ✅ Yes | ❌ None |
| **Direct `~/.aws/credentials` Sync** | ✅ **Atomic & `0600`** | ❌ Token cache only | ⚠️ Shell wrapper | ⚠️ Keyring / Env wrapper |
| **Universal Tool Compatibility (Terraform, Docker, Helm)** | ✅ **100% Out of Box** | ⚠️ Many tools fail without STS keys | ⚠️ Requires `assume` wrapper | ⚠️ Requires `exec` wrapper |
| **Native WSL2 -> Windows Browser Bridge** | ✅ **Automatic** | ❌ Fails / manual URL copy | ⚠️ Partial | ❌ No |
| **Integrated EC2 SSM & EKS Context Switching** | ✅ **Built-in** | ❌ Separate commands | ❌ Separate commands | ❌ No |
| **AWS `credential_process` Standard** | ✅ **Full support** | ❌ N/A | ⚠️ Yes | ⚠️ Yes |
| **Lightweight Standalone Binaries** | ✅ **Zero dependencies** | ❌ Requires Python/AWS CLI | ⚠️ Go binary | ⚠️ Go binary |

---

## Deep Dive: Key Advantages

### 1. No More Tedious `~/.aws/config` Files
The official AWS CLI requires maintaining dozens of profile blocks in `~/.aws/config`:
```ini
# You don't need to write 50 blocks like this anymore:
[profile production-app-admin]
sso_start_url = https://my-org.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = AdministratorAccess
```
With `aws-auth`, you only provide your SSO Start URL once. It discovers all accessible accounts and roles dynamically.

### 2. Built for the AI Pair-Programming Era (MCP)
`aws-auth` is the **first AWS authentication and profile manager equipped with a Model Context Protocol (MCP) server**.
AI assistants (like Claude, Cursor, Antigravity) can seamlessly query active caller identities, inspect EC2 instances, list EKS clusters, and switch roles with zero credential leakage.

### 3. Immediate Compatibility with Legacy & GUI Tooling
Many enterprise tools (older Terraform providers, JetBrains IDE plugins, Docker desktop credential helpers, Lens for Kubernetes) do not support modern AWS SSO token exchange natively and demand valid session keys in `~/.aws/credentials`. `aws-auth` writes temporary STS credentials atomically and securely, ensuring all tools work without wrappers.
