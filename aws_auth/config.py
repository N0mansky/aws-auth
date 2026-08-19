import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class Config:
    """Configuration management class with validation, environment variables, and user configuration."""
    
    def __init__(self):
        self.AWS_SSO_CACHE_DIR = os.path.expanduser("~/.aws/sso/cache")
        self.CACHE_DIR = os.path.expanduser("~/.aws-auth")
        self.AUTHLY_DIR = self.CACHE_DIR  # Alias for backwards compatibility
        self.CONFIG_FILE = os.path.join(self.CACHE_DIR, "config.json")
        self.CLIENT_CACHE_FILE = os.path.join(self.CACHE_DIR, "client_cache.json")
        
        user_config = self._load_user_config()
        
        self.SSO_START_URL = (
            os.environ.get("AWS_SSO_START_URL")
            or user_config.get("sso_start_url")
            or os.environ.get("SSO_START_URL")
            or ""
        )
        self.SSO_REGION = (
            os.environ.get("AWS_SSO_REGION")
            or user_config.get("sso_region")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.CLIENT_NAME = user_config.get("client_name") or "aws-auth-sso-app"
        self.SESSION_DURATION_SECONDS = 43200  # 12 hours fallback
        
        # Client registration parameters
        self.CLIENT_TYPE = "public"
        self.CLIENT_SCOPES = ["sso:account:access"]
        self.CLIENT_GRANT_TYPES = [
            "urn:ietf:params:oauth:grant-type:device_code",
            "refresh_token"
        ]

    def _load_user_config(self) -> Dict[str, Any]:
        """Load user-defined configuration from ~/.aws-auth/config.json or existing cached token."""
        result = {}
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    result.update(json.load(f))
            except Exception as e:
                logger.debug(f"Could not load config file {self.CONFIG_FILE}: {e}")
        
        # If not explicitly configured, reuse startUrl and region from existing cached token
        if not result.get("sso_start_url"):
            token_file = os.path.join(self.CACHE_DIR, "sso_access_token.json")
            if os.path.exists(token_file):
                try:
                    with open(token_file, "r") as f:
                        token_data = json.load(f)
                        if token_data.get("startUrl"):
                            result["sso_start_url"] = token_data["startUrl"]
                        if token_data.get("region"):
                            result["sso_region"] = token_data["region"]
                except Exception:
                    pass
        return result

    def save_user_config(self, sso_start_url: str, sso_region: str = "us-east-1") -> None:
        """Save user configuration to ~/.aws-auth/config.json."""
        os.makedirs(self.CACHE_DIR, mode=0o700, exist_ok=True)
        user_config = self._load_user_config()
        user_config["sso_start_url"] = sso_start_url
        user_config["sso_region"] = sso_region
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(user_config, f, indent=2)
        try:
            os.chmod(self.CONFIG_FILE, 0o600)
        except (OSError, NotImplementedError):
            pass
        self.SSO_START_URL = sso_start_url
        self.SSO_REGION = sso_region

    def get_recent_selections(self) -> list:
        """Get list of recently selected account/role combinations."""
        user_config = self._load_user_config()
        return user_config.get("recent_selections", [])

    def record_recent_selection(self, account_id: str, account_name: str, role_name: str) -> None:
        """Record an account/role selection to the top of MRU list in config.json."""
        user_config = self._load_user_config()
        recents = user_config.get("recent_selections", [])
        
        entry = {"accountId": str(account_id), "accountName": str(account_name), "roleName": str(role_name)}
        recents = [r for r in recents if not (str(r.get("accountId")) == str(account_id) and str(r.get("roleName")) == str(role_name))]
        recents.insert(0, entry)
        user_config["recent_selections"] = recents[:10]  # Keep last 10
        
        os.makedirs(self.CACHE_DIR, mode=0o700, exist_ok=True)
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(user_config, f, indent=2)
            os.chmod(self.CONFIG_FILE, 0o600)
        except Exception as e:
            logger.debug(f"Could not save recent selection: {e}")

    def get_aliases(self) -> Dict[str, str]:
        """Get account ID to display alias mapping."""
        user_config = self._load_user_config()
        return user_config.get("aliases", {})

    def get_preferred_accounts(self) -> list:
        """Get list of preferred account names or IDs."""
        user_config = self._load_user_config()
        return user_config.get("preferred_accounts", [])

    def prompt_for_config_if_missing(self) -> bool:
        """Prompt user interactively if SSO_START_URL is not configured."""
        if not self.SSO_START_URL:
            import sys
            if not sys.stdin.isatty():
                return False
            try:
                print("\n⚙️  AWS SSO Setup (First-Time Configuration):")
                print("Enter your AWS IAM Identity Center (SSO) Start URL.")
                print("Example: https://my-company.awsapps.com/start\n")
                url = input("AWS SSO Start URL: ").strip()
                if url:
                    region = input(f"AWS SSO Region [default: {self.SSO_REGION}]: ").strip() or self.SSO_REGION
                    self.save_user_config(url, region)
                    print(f"✅ Configuration saved to {self.CONFIG_FILE}\n")
                    return True
                else:
                    print("❌ Error: SSO Start URL cannot be empty.")
                    return False
            except (KeyboardInterrupt, EOFError):
                print("\nConfiguration cancelled.")
                return False
        return True

    def validate(self) -> bool:
        """Validate configuration settings."""
        required_attrs = ['SSO_REGION', 'CLIENT_NAME', 'SSO_START_URL']
        for attr in required_attrs:
            if not getattr(self, attr):
                logger.error(f"Configuration error: {attr} is required")
                return False
        return True
