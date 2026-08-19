# AWS Auth - Package Architecture

## 📁 Package Structure

The `aws_auth` package is structured into cohesive, single-responsibility modules:

```
aws_auth/
├── __init__.py             # Package exports & version info
├── __main__.py             # Execution entry point (`python -m aws_auth`)
├── cli.py                  # Argument parsing and CLI dispatch
├── auth_manager.py         # Main authentication orchestrator
├── caller_identity.py      # STS caller identity validator
├── config.py               # Centralized configuration & defaults
├── credentials_manager.py  # ~/.aws/credentials file management
├── ec2_manager.py          # EC2 querying & SSM connection handler
├── eks_manager.py          # EKS cluster discovery & kubeconfig update
├── local_browser_manager.py# Cross-platform browser launcher (Linux, macOS, WSL2, Windows)
├── profile_manager.py      # Interactive profile management
├── sso_client.py           # AWS SSO OIDC protocol interaction
├── token_manager.py        # Token caching & lifecycle operations
└── user_interface.py       # Terminal UI formatting and interactive prompts
```

## 🏗️ Module Descriptions

### `config.py` - Configuration Management
- **Class**: `Config`
- **Purpose**: Centralized configuration with validation
- **Features**: SSO start URL, regions, cache paths, session durations

### `token_manager.py` - Token Operations
- **Class**: `TokenManager`
- **Purpose**: Manages SSO token lifecycle
- **Features**: Token caching in `~/.aws-auth/`, expiration checks, OIDC client registration caching

### `local_browser_manager.py` - Browser Launcher
- **Class**: `LocalBrowserManager`
- **Purpose**: Opens SSO authorization URLs directly in default browser
- **Features**: Automatic WSL2 detection to launch the host Windows browser

### `sso_client.py` - AWS SSO Operations
- **Class**: `SSOClient`
- **Purpose**: Interacts with AWS SSO and OIDC APIs
- **Features**: Device authorization flow, account listing, role listing, credential retrieval

### `credentials_manager.py` - Credentials Management
- **Class**: `CredentialsManager`
- **Purpose**: Manages standard AWS credentials files (`~/.aws/credentials`)
- **Features**: Safe INI writing, multi-profile support, default profile toggling

### `ec2_manager.py` - EC2 & SSM Session Integration
- **Class**: `EC2Manager`
- **Purpose**: Discovers running EC2 instances and initiates SSM sessions
- **Features**: Filter running instances, generate SSH commands, seamless SSM terminal attachment

### `eks_manager.py` - EKS Integration
- **Class**: `EKSManager`
- **Purpose**: Discovers EKS clusters and updates kubeconfig
- **Features**: Cluster listing, kubeconfig synchronization

### `user_interface.py` - User Interaction
- **Class**: `UserInterface`
- **Purpose**: Handles terminal menus, formatted tables, and user prompts

### `profile_manager.py` - Profile Operations
- **Class**: `ProfileManager`
- **Purpose**: Interactive profile management (list, switch, set default, delete)

### `auth_manager.py` - Orchestration
- **Class**: `AuthManager`
- **Purpose**: Coordinates all components to perform end-to-end SSO authentication

---

## 🧪 Testing

Run test suite:
```bash
python3 -m unittest discover tests
```
