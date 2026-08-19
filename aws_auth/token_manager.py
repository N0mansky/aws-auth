"""Token management for AWS SSO authentication."""

import os
import glob
import json
import time
import logging
import boto3
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any, List

from .config import Config

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages SSO token operations including caching, loading, and validation."""
    
    # 5-minute safety buffer before token expiration to prevent race conditions
    EXPIRATION_MARGIN_SECONDS: int = 300
    
    def __init__(self, config: Config):
        self.config = config
        self._ensure_cache_dir()
        self._token_info_cache: Optional[Dict[str, Any]] = None
        self._token_info_cache_time: Optional[float] = None
        self._token_info_cache_ttl: float = 5.0  # Cache for 5 seconds to avoid redundant scans
        self._sso_client_cache = None  # Cache boto3 client for validation
    
    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists with restricted 0700 permissions."""
        os.makedirs(self.config.AUTHLY_DIR, mode=0o700, exist_ok=True)
        try:
            os.chmod(self.config.AUTHLY_DIR, 0o700)
        except (OSError, NotImplementedError):
            pass

    def _secure_file_permissions(self, file_path: str) -> None:
        """Ensure token file has strict 0600 permissions."""
        try:
            if os.path.exists(file_path):
                os.chmod(file_path, 0o600)
        except (OSError, NotImplementedError):
            pass

    def _atomic_write_json(self, data: Dict[str, Any], file_path: str) -> None:
        """Atomically write JSON data to file with 0600 permissions."""
        self._ensure_cache_dir()
        dir_name = os.path.dirname(file_path)
        os.makedirs(dir_name, mode=0o700, exist_ok=True)
        temp_path = f"{file_path}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
        try:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            self._secure_file_permissions(temp_path)
            os.replace(temp_path, file_path)
            self._secure_file_permissions(file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            logger.error(f"Failed to atomically write {file_path}: {e}")
            raise
    
    def load_registered_client(self) -> Tuple[Optional[str], Optional[str]]:
        """Load cached OIDC client credentials if they exist and are valid."""
        if not os.path.exists(self.config.CLIENT_CACHE_FILE):
            return None, None
            
        try:
            with open(self.config.CLIENT_CACHE_FILE, "r") as f:
                data = json.load(f)
                # Check if client secret has expired - support both new and legacy formats
                client_secret_expires_at = data.get("clientSecretExpiresAt") or data.get("expiresAt", 0)
                if time.time() < client_secret_expires_at:
                    return data["clientId"], data["clientSecret"]
                else:
                    expiry_time = datetime.fromtimestamp(client_secret_expires_at) if client_secret_expires_at > 0 else "unknown"
                    logger.info(f"Cached client secret expired at {expiry_time}")
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Failed to load registered client: {e}")
        
        return None, None
    
    def save_registered_client(self, client_id: str, client_secret: str, 
                              client_id_issued_at: Optional[int] = None,
                              client_secret_expires_at: Optional[int] = None,
                              token_endpoint: Optional[str] = None) -> None:
        """Save OIDC client credentials and metadata to cache."""
        data = {
            "clientId": client_id,
            "clientSecret": client_secret,
        }
        
        # Add optional metadata from register_client response
        if client_id_issued_at is not None:
            data["clientIdIssuedAt"] = client_id_issued_at
        if client_secret_expires_at is not None:
            data["clientSecretExpiresAt"] = client_secret_expires_at
        if token_endpoint:
            data["tokenEndpoint"] = token_endpoint
            
        self._atomic_write_json(data, self.config.CLIENT_CACHE_FILE)
    
    def cache_sso_access_token(self, access_token: str, expires_in: int, refresh_token: Optional[str] = None) -> None:
        """Cache SSO access token and refresh token with expiration information.
        
        Uses a fixed filename - replaces the old token file if it exists.
        """
        cache_entry = {
            "startUrl": self.config.SSO_START_URL,
            "region": self.config.SSO_REGION,
            "accessToken": access_token,
            "expiresAt": datetime.fromtimestamp(
                time.time() + expires_in - 60, tz=timezone.utc  # Use actual expires_in from AWS, minus 60 second buffer
            ).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        
        # Add refresh token if provided
        if refresh_token:
            cache_entry["refreshToken"] = refresh_token
        
        # Use fixed filename - replace old token if it exists
        filename = os.path.join(self.config.AUTHLY_DIR, "sso_access_token.json")
        
        # Clean up any old timestamped token files
        self._cleanup_old_token_files()
        
        try:
            self._atomic_write_json(cache_entry, filename)
            logger.info(f"Cached SSO token at: {filename}")
            if refresh_token:
                logger.info("Refresh token cached for future use")
            # Invalidate cache since we just added a new token
            self._token_info_cache = None
            self._token_info_cache_time = None
        except OSError as e:
            logger.error(f"Failed to cache SSO token: {e}")
            raise
    
    def _cleanup_old_token_files(self) -> None:
        """Remove old timestamped token files (migration helper - keep only fixed filename)."""
        import glob
        token_pattern = os.path.join(self.config.AUTHLY_DIR, "cached_token_*.json")
        removed_count = 0
        
        for filename in glob.glob(token_pattern):
            try:
                os.remove(filename)
                removed_count += 1
                logger.debug(f"Removed old token file: {filename}")
            except OSError as e:
                logger.debug(f"Could not remove old token file {filename}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old token file(s)")
    
    def cleanup_expired_tokens(self, force: bool = False) -> None:
        """Remove expired token file if it exists.
        
        Args:
            force: If True, always run cleanup. If False, may skip if recently run.
        """
        # Throttle cleanup to avoid running on every token check
        # Only run if forced or if we haven't run cleanup recently
        if not force and hasattr(self, '_last_cleanup_time'):
            time_since_cleanup = time.time() - self._last_cleanup_time
            if time_since_cleanup < 60:  # Skip if cleaned up in last 60 seconds
                logger.debug("Skipping cleanup - ran recently")
                return
        
        current_time = datetime.now(timezone.utc)
        token_file = os.path.join(self.config.AUTHLY_DIR, "sso_access_token.json")
        removed_count = 0
        
        if os.path.exists(token_file):
            try:
                with open(token_file, "r") as f:
                    data = json.load(f)
                    expires_at = data.get("expiresAt")
                    
                    if not expires_at:
                        # Invalid token file - remove it
                        os.remove(token_file)
                        removed_count += 1
                        logger.info(f"Removed invalid token file: {token_file}")
                    else:
                        expiry_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        if expiry_dt.tzinfo is None:
                            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                            
                        if expiry_dt <= current_time:
                            # Check if token has a refresh token before removing
                            refresh_token = data.get("refreshToken")
                            if refresh_token:
                                logger.debug(f"Keeping expired token file - has refresh token for renewal")
                            else:
                                os.remove(token_file)
                                removed_count += 1
                                logger.info(f"Removed expired token file: {token_file}")
                        
            except (json.JSONDecodeError, KeyError, OSError, ValueError) as e:
                logger.warning(f"Could not process {token_file} for cleanup: {e}")
        
        self._last_cleanup_time = time.time()
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired token file(s)")
            # Invalidate cache after cleanup
            self._token_info_cache = None
            self._token_info_cache_time = None
    
    def get_token_info(self, sso_start_url: Optional[str] = None, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get token information including expiration status and refresh token availability.
        
        Args:
            sso_start_url: SSO start URL to match tokens against
            use_cache: Whether to use cached token info (default: True)
        
        Returns:
            Dict with keys: 'accessToken', 'isExpired', 'hasRefreshToken', 'refreshToken'
            or None if no token found
        """
        if sso_start_url is None:
            sso_start_url = self.config.SSO_START_URL
        
        # Return cached result if available and still valid
        if use_cache and self._token_info_cache is not None and self._token_info_cache_time is not None:
            if time.time() - self._token_info_cache_time < self._token_info_cache_ttl:
                cached_url = self._token_info_cache.get('_cached_url', '')
                if cached_url == sso_start_url.rstrip("/"):
                    logger.debug("Returning cached token info")
                    # Return a copy without the cache metadata
                    result = self._token_info_cache.copy()
                    result.pop('_cached_url', None)
                    return result
            
        token_file = os.path.join(self.config.AUTHLY_DIR, "sso_access_token.json")
        current_time = datetime.now(timezone.utc)
        normalized_start_url = sso_start_url.rstrip("/")
        
        valid_token_info = None
        expired_token_info = None
        
        # Check fixed token file first, then check for old timestamped files (migration)
        token_files = [token_file] if os.path.exists(token_file) else []
        # Also check for old timestamped files (for migration)
        old_token_pattern = os.path.join(self.config.AUTHLY_DIR, "cached_token_*.json")
        token_files.extend(glob.glob(old_token_pattern))
        
        for filename in token_files:
            try:
                with open(filename, "r") as f:
                    data = json.load(f)
                    
                file_start_url = data.get("startUrl", "").rstrip("/")
                if file_start_url != normalized_start_url:
                    continue
                    
                expires_at = data.get("expiresAt")
                if not expires_at:
                    continue
                    
                access_token = data.get("accessToken")
                refresh_token = data.get("refreshToken")
                
                # Parse the expiration time as UTC and make it timezone-aware
                expiry_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                
                # Check expiration with safety margin buffer
                effective_expiry = expiry_dt.timestamp() - self.EXPIRATION_MARGIN_SECONDS
                is_expired = time.time() >= effective_expiry

                token_info = {
                    'accessToken': access_token,
                    'isExpired': is_expired,
                    'hasRefreshToken': bool(refresh_token),
                    'refreshToken': refresh_token,
                    'expiresAt': expiry_dt
                }
                
                if not is_expired:
                    valid_token_info = token_info
                    logger.info(f"Valid token found in {filename}, expires at {expiry_dt}")
                else:
                    logger.info(f"Token in {filename} has expired (or within 5m safety margin) at {expiry_dt}")
                    if refresh_token and expired_token_info is None:
                        expired_token_info = token_info
                        logger.info(f"Expired token has refresh token - can be refreshed")
                    
            except (json.JSONDecodeError, KeyError, OSError, ValueError) as e:
                logger.warning(f"Could not read or parse {filename}: {e}")
        
        # Return valid token if found, otherwise return expired token with refresh token
        result = None
        if valid_token_info:
            result = valid_token_info
        elif expired_token_info:
            logger.info("No valid tokens found, but expired token with refresh token available for refresh attempt")
            result = expired_token_info
        
        # Cache the result for future calls
        if use_cache and result is not None:
            self._token_info_cache = result.copy()
            self._token_info_cache['_cached_url'] = normalized_start_url
            self._token_info_cache_time = time.time()
        
        return result
    
    def load_token(self, sso_start_url: Optional[str] = None) -> Optional[str]:
        """Load a valid cached SSO token matching the given start URL."""
        token_info = self.get_token_info(sso_start_url)
        if token_info and not token_info.get('isExpired'):
            logger.info(f"Looking for SSO token matching startUrl={sso_start_url or self.config.SSO_START_URL}")
            return token_info.get('accessToken')
        return None
    
    def load_refresh_token(self, sso_start_url: Optional[str] = None) -> Optional[str]:
        """Load a cached refresh token if available."""
        if sso_start_url is None:
            sso_start_url = self.config.SSO_START_URL
            
        token_file = os.path.join(self.config.AUTHLY_DIR, "sso_access_token.json")
        normalized_start_url = sso_start_url.rstrip("/")
        
        # Check fixed token file first, then check for old timestamped files (migration)
        token_files = [token_file] if os.path.exists(token_file) else []
        old_token_pattern = os.path.join(self.config.AUTHLY_DIR, "cached_token_*.json")
        token_files.extend(glob.glob(old_token_pattern))
        
        for filename in token_files:
            try:
                with open(filename, "r") as f:
                    data = json.load(f)
                    
                file_start_url = data.get("startUrl", "").rstrip("/")
                if file_start_url != normalized_start_url:
                    continue
                    
                refresh_token = data.get("refreshToken")
                if refresh_token:
                    logger.info(f"Found refresh token in {filename}")
                    return refresh_token
                    
            except (json.JSONDecodeError, KeyError, OSError, ValueError) as e:
                logger.warning(f"Could not read or parse {filename}: {e}")
                
        logger.debug("No refresh token found in cache")
        return None
    
    def is_token_expired(self, access_token: str, sso_start_url: Optional[str] = None) -> bool:
        """Check if a token is expired with safety margin."""
        if sso_start_url is None:
            sso_start_url = self.config.SSO_START_URL
            
        token_file = os.path.join(self.config.AUTHLY_DIR, "sso_access_token.json")
        normalized_start_url = sso_start_url.rstrip("/")
        
        # Check fixed token file first, then check for old timestamped files (migration)
        token_files = [token_file] if os.path.exists(token_file) else []
        old_token_pattern = os.path.join(self.config.AUTHLY_DIR, "cached_token_*.json")
        token_files.extend(glob.glob(old_token_pattern))
        
        for filename in token_files:
            try:
                with open(filename, "r") as f:
                    data = json.load(f)
                    
                file_start_url = data.get("startUrl", "").rstrip("/")
                if file_start_url != normalized_start_url:
                    continue
                    
                if data.get("accessToken") != access_token:
                    continue
                    
                expires_at = data.get("expiresAt")
                if not expires_at:
                    continue
                    
                expiry_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                    
                effective_expiry = expiry_dt.timestamp() - self.EXPIRATION_MARGIN_SECONDS
                return time.time() >= effective_expiry
                    
            except (json.JSONDecodeError, KeyError, OSError, ValueError):
                continue
        
        # If we can't find the token in cache, assume it's expired to be safe
        return True
    
    def validate_access_token(self, access_token: str) -> bool:
        """Validate the access token by making a test API call."""
        try:
            # Lazy import boto3 for speed
            import boto3
            if self._sso_client_cache is None:
                self._sso_client_cache = boto3.client("sso", region_name=self.config.SSO_REGION)
            self._sso_client_cache.list_accounts(accessToken=access_token, maxResults=1)
            return True
        except Exception as e:
            logger.debug(f"Token validation failed: {e}")
            self._sso_client_cache = None
            return False
    
    def remove_invalid_token(self, invalid_token: str) -> None:
        """Remove the specified invalid token from cache."""
        token_file = os.path.join(self.config.AUTHLY_DIR, "sso_access_token.json")
        
        token_files = [token_file] if os.path.exists(token_file) else []
        old_token_pattern = os.path.join(self.config.AUTHLY_DIR, "cached_token_*.json")
        token_files.extend(glob.glob(old_token_pattern))
        
        for filename in token_files:
            try:
                with open(filename, "r") as f:
                    data = json.load(f)
                    if data.get("accessToken") == invalid_token:
                        os.remove(filename)
                        logger.info(f"Removed invalid token file: {filename}")
                        self._token_info_cache = None
                        self._token_info_cache_time = None
                        return
            except (json.JSONDecodeError, OSError):
                continue

    def cache_accounts_and_roles(self, accounts: List[Dict[str, Any]], all_account_roles: Dict[str, List[Dict[str, Any]]]) -> None:
        """Cache discovered accounts and roles list to speed up subsequent logins."""
        cache_file = os.path.join(self.config.AUTHLY_DIR, "accounts_cache.json")
        data = {
            "cached_at": time.time(),
            "startUrl": self.config.SSO_START_URL,
            "accounts": accounts,
            "roles": all_account_roles
        }
        try:
            self._atomic_write_json(data, cache_file)
            logger.debug("Successfully cached accounts and roles list")
        except Exception as e:
            logger.warning(f"Could not cache accounts list: {e}")

    def load_cached_accounts_and_roles(self, max_age_hours: int = 24) -> Optional[Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]]:
        """Load cached accounts and roles if available and within TTL."""
        cache_file = os.path.join(self.config.AUTHLY_DIR, "accounts_cache.json")
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > (max_age_hours * 3600):
                logger.debug("Accounts cache expired")
                return None
            
            if data.get("startUrl", "").rstrip("/") != self.config.SSO_START_URL.rstrip("/"):
                return None
            
            accounts = data.get("accounts")
            roles = data.get("roles")
            if accounts and roles:
                return accounts, roles
        except Exception as e:
            logger.debug(f"Failed to read accounts cache: {e}")
        
        return None
