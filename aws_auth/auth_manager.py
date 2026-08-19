"""Main authentication manager for AWS SSO."""

import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Tuple

from .config import Config
from .token_manager import TokenManager
from .local_browser_manager import LocalBrowserManager
from .sso_client import SSOClient
from .credentials_manager import CredentialsManager
from .user_interface import UserInterface
from .ec2_manager import EC2Manager
from .eks_manager import EKSManager

logger = logging.getLogger(__name__)


from dataclasses import dataclass

@dataclass
class AuthResult:
    """Result of a successful AWS SSO role assumption and credential write."""
    profile_names: List[str]
    credentials: Dict[str, str]
    region: str
    account: Dict[str, Any]
    role: Dict[str, Any]
    set_as_default: bool = True


class AuthManager:
    """Main authentication manager that orchestrates the entire SSO process."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        if not self.config.validate():
            raise ValueError("Invalid configuration")
        
        self.token_manager = TokenManager(self.config)
        self.browser_manager = LocalBrowserManager(self.config)
        self.sso_client = SSOClient(self.config)
        self.credentials_manager = CredentialsManager()
        self.ui = UserInterface()
    
    def get_valid_access_token(self, username: Optional[str] = None, password: Optional[str] = None) -> str:
        """Get a valid access token, refreshing if necessary."""
        # Clean up expired tokens (throttled - won't run if done recently)
        self.token_manager.cleanup_expired_tokens()
        
        # Get token information including expiration status (uses cache)
        token_info = self.token_manager.get_token_info()
        
        if token_info:
            access_token = token_info.get('accessToken')
            is_expired = token_info.get('isExpired', True)
            has_refresh_token = token_info.get('hasRefreshToken', False)
            
            # If token is not expired, trust the expiration time (skip expensive API validation)
            # Only validate if token is close to expiration or if explicitly needed
            # This optimization avoids unnecessary API calls for recently cached tokens
            if not is_expired:
                # Trust cached expiration time - skip validation for performance
                # Token validation is expensive (API call) and expiration time is reliable
                logger.info("Reusing cached valid access token")
                return access_token
            
            # Token is expired or invalid - try to refresh if refresh token is available
            if is_expired and has_refresh_token:
                logger.info("🔄 Cached token is expired, attempting to refresh using refresh token...")
                logger.info("   (This will skip device code generation and browser authentication)")
                refreshed_token = self._attempt_token_refresh()
                if refreshed_token:
                    logger.info("✅ Successfully refreshed access token (no device code needed!)")
                    return refreshed_token
                else:
                    logger.info("⚠️  Token refresh failed, refresh token may be invalid or expired")
                    logger.info("   Falling back to device code flow...")
                    # Remove invalid token to prevent retrying with same refresh token
                    self.token_manager.remove_invalid_token(access_token)
            elif is_expired:
                logger.info("⚠️  Token is expired and no refresh token available")
                logger.info("   Reason: AWS SSO may not have provided a refresh token, or it expired")
                logger.info("   Will need to generate new device code (browser will use your existing cookies/sessions)")
                # Remove expired token without refresh token
                self.token_manager.remove_invalid_token(access_token)
        
        # No valid token or refresh failed - perform fresh login
        logger.info("🔐 Performing fresh SSO login...")
        logger.info("   Your browser will open - complete authentication there (uses your cookies/sessions)")
        return self._perform_sso_login(username, password)
    
    def _perform_sso_login(self, username: Optional[str] = None, password: Optional[str] = None) -> str:
        """Perform SSO login and return access token."""
        # For local browser, we don't need credentials upfront
        # User will authenticate in their browser using existing cookies/sessions
        # Keep username/password params for compatibility but they're not used
        
        # Register OIDC client
        client_id, client_secret = self.sso_client.register_client(self.token_manager)
        
        # Use device code flow (standard for CLI tools)
        logger.info("🔐 Starting AWS SSO device authorization...")
        logger.info("   Your browser will open - complete authentication there (uses your cookies/sessions)")
        authz = self.sso_client.start_device_authorization(client_id, client_secret)
        logger.info(f"   Device code: {authz.get('userCode', 'N/A')}")
        logger.info(f"   Visit: {authz.get('verificationUriComplete', 'N/A')[:80]}...")
        
        # Perform browser login (opens local browser)
        self.browser_manager.perform_sso_login(authz["verificationUriComplete"])
        
        # Poll for token
        expires = time.time() + authz["expiresIn"]
        interval = authz["interval"]
        poll_count = 0

        logger.info("Polling for device authorization token...")
        while time.time() < expires:
            try:
                token_response = self.sso_client.create_device_token(
                    client_id, client_secret, authz["deviceCode"]
                )
                access_token = token_response["accessToken"]
                refresh_token = token_response.get("refreshToken")
                expires_in = token_response.get("expiresIn")
                if expires_in is None:
                    expires_in = self.config.SESSION_DURATION_SECONDS
                    logger.warning(f"AWS did not return expiresIn, using fallback: {expires_in} seconds")
                logger.info(f"SSO login complete - token expires in {expires_in} seconds ({expires_in/3600:.1f} hours)")
                
                # Log refresh token status
                if refresh_token:
                    logger.info("✅ Refresh token received - next login can skip device code if token is still valid")
                    logger.info("   (Browser cookies will still skip Microsoft authentication)")
                else:
                    logger.warning("⚠️  No refresh token received from AWS SSO")
                    logger.warning("   Next login will require new device code (but browser cookies will skip Microsoft login)")
                
                self.token_manager.cache_sso_access_token(access_token, expires_in, refresh_token)
                return access_token
            except self.sso_client.oidc_client.exceptions.AuthorizationPendingException:
                poll_count += 1
                # Show progress every 3 polls to avoid spam
                if poll_count % 3 == 0:
                    remaining = int(expires - time.time())
                    logger.info(f"⏳ Still waiting... ({remaining}s remaining)")
                time.sleep(interval)
            except self.sso_client.oidc_client.exceptions.ExpiredTokenException:
                raise RuntimeError("Login timed out")
            except Exception as e:
                raise RuntimeError(f"Login failed: {e}")

        raise RuntimeError("Device code expired before authorization")
    
    def _attempt_token_refresh(self) -> Optional[str]:
        """Attempt to refresh the access token using a cached refresh token."""
        try:
            # Try to load refresh token from token info first (more reliable)
            token_info = self.token_manager.get_token_info()
            if not token_info or not token_info.get('hasRefreshToken'):
                # Fallback to direct refresh token load
                refresh_token = self.token_manager.load_refresh_token()
                if not refresh_token:
                    logger.debug("No refresh token available")
                    return None
            else:
                refresh_token = token_info.get('refreshToken')
            
            # Get client credentials
            client_id, client_secret = self.sso_client.register_client(self.token_manager)
            if not client_id or not client_secret:
                logger.error("Could not get client credentials for token refresh")
                return None
            
            # Attempt to refresh the token
            logger.info("Attempting to refresh access token...")
            token_response = self.sso_client.refresh_access_token(
                client_id, client_secret, refresh_token
            )
            
            # Cache the new tokens
            access_token = token_response["accessToken"]
            new_refresh_token = token_response.get("refreshToken", refresh_token)  # Use new or fallback to old
            expires_in = token_response.get("expiresIn")
            if expires_in is None:
                expires_in = self.config.SESSION_DURATION_SECONDS
                logger.warning(f"AWS did not return expiresIn during refresh, using fallback: {expires_in} seconds")
            
            logger.info(f"Token refreshed successfully - expires in {expires_in} seconds ({expires_in/3600:.1f} hours)")
            self.token_manager.cache_sso_access_token(access_token, expires_in, new_refresh_token)
            
            # Clean up old expired token files after successful refresh (force cleanup)
            self.token_manager.cleanup_expired_tokens(force=True)
            
            return access_token
            
        except self.sso_client.oidc_client.exceptions.InvalidGrantException as e:
            logger.info(f"Token refresh failed: Refresh token is invalid or expired - {e}")
            return None
        except self.sso_client.oidc_client.exceptions.ExpiredTokenException as e:
            logger.info(f"Token refresh failed: Refresh token has expired - {e}")
            return None
        except Exception as e:
            logger.info(f"Token refresh failed: {e}")
            return None
    
    def assume_role_via_sso(self, force_refresh_accounts: bool = False) -> AuthResult:
        """Perform SSO login, choose account/role, write credentials, and return AuthResult."""
        # Get valid access token
        access_token = self.get_valid_access_token()
        
        accounts = None
        all_account_roles = None
        
        # Try loading cached accounts & roles if not force refreshing
        if not force_refresh_accounts:
            cached_data = self.token_manager.load_cached_accounts_and_roles()
            if cached_data:
                accounts, all_account_roles = cached_data
                logger.info("Using cached accounts and roles list (use --refresh-cache to update)")
        
        if not accounts or not all_account_roles:
            # Get available accounts
            accounts = self.sso_client.list_accounts(access_token)
            if not accounts:
                raise RuntimeError("No accounts available.")
            
            # Get roles for all accounts (parallelized for better performance)
            logger.info("Loading roles for all accounts...")
            all_account_roles = {}
            total_combinations = 0
            
            def fetch_roles_for_account(account: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
                """Fetch roles for a single account. Returns (account_id, roles, error_message)."""
                account_id = account["accountId"]
                account_name = account["accountName"]
                try:
                    roles = self.sso_client.list_account_roles(access_token, account_id)
                    if roles:
                        roles.sort(key=lambda role: role['roleName'])
                        return account_id, roles, None
                    else:
                        return account_id, [], f"No roles available for account {account_name}"
                except Exception as e:
                    return account_id, [], f"Failed to get roles for {account_name}: {e}"
            
            # Fetch roles in parallel if multiple accounts, otherwise sequential
            if len(accounts) > 1:
                with ThreadPoolExecutor(max_workers=min(5, len(accounts))) as executor:
                    future_to_account = {
                        executor.submit(fetch_roles_for_account, account): account 
                        for account in accounts
                    }
                    
                    for future in as_completed(future_to_account):
                        account_id, roles, error_msg = future.result()
                        if error_msg:
                            logger.warning(error_msg)
                        if roles:
                            all_account_roles[account_id] = roles
                            total_combinations += len(roles)
                            logger.debug(f"Found {len(roles)} role(s) for account {account_id}")
            else:
                for account in accounts:
                    account_id, roles, error_msg = fetch_roles_for_account(account)
                    if error_msg:
                        logger.warning(error_msg)
                    if roles:
                        all_account_roles[account_id] = roles
                        total_combinations += len(roles)
                        logger.debug(f"Found {len(roles)} role(s) for {account['accountName']}")
            
            if total_combinations == 0:
                raise RuntimeError("No account-role combinations available.")
            
            # Cache discovered accounts and roles
            self.token_manager.cache_accounts_and_roles(accounts, all_account_roles)
        
        # Count total combinations
        total_combinations = sum(len(roles) for roles in all_account_roles.values())
        
        # Handle single vs multiple combinations
        selected_region = "us-east-1"  # Default region
        if total_combinations == 1:
            for account in accounts:
                account_id = account["accountId"]
                if account_id in all_account_roles and all_account_roles[account_id]:
                    selected_account = account
                    selected_role = all_account_roles[account_id][0]
                    logger.info(f"Using single available combination: {selected_account['accountName']} - {selected_role['roleName']}")
                    break
        else:
            selected_account, selected_role, selected_region = self.ui.select_account_and_role(accounts, all_account_roles)
        
        # Get role credentials
        creds = self.sso_client.get_role_credentials(
            access_token, 
            selected_account["accountId"], 
            selected_role["roleName"]
        )
        
        # Get user preferences and write credentials
        existing_profiles = list(self.credentials_manager.get_existing_profiles())
        profile_names, region, set_as_default = self.ui.get_user_preferences(
            existing_profiles,
            account_name=selected_account["accountName"],
            role_name=selected_role["roleName"],
            region=selected_region
        )
        self.credentials_manager.write_credentials(profile_names, creds, region)
        
        if len(profile_names) == 1:
            profile_name = profile_names[0]
            if self.credentials_manager.set_default_profile(profile_name):
                logger.info(f"Profile '{profile_name}' set as default.")
            else:
                logger.warning(f"Failed to set '{profile_name}' as default.")
        
        logger.info("AWS credentials updated. You can now use the AWS CLI with the selected profile.")
        if len(profile_names) == 1:
            profile_name = profile_names[0]
            if profile_name == 'default' or set_as_default:
                logger.info("Credentials saved to default profile. Use: aws sts get-caller-identity")
            else:
                logger.info(f"Credentials saved to profile '{profile_name}'. Use: aws --profile {profile_name} sts get-caller-identity")
        else:
            logger.info(f"Credentials saved to profiles: {', '.join(profile_names)}")
            for profile_name in profile_names:
                if profile_name != 'default':
                    logger.info(f"  Use profile '{profile_name}': aws --profile {profile_name} sts get-caller-identity")
        
        return AuthResult(
            profile_names=profile_names,
            credentials=creds,
            region=region,
            account=selected_account,
            role=selected_role,
            set_as_default=set_as_default
        )
    
