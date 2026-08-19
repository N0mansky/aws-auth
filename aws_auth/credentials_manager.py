"""AWS credentials file management."""

import os
import time
import configparser
import logging
import shutil
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)


class CredentialsManager:
    """Manages AWS credentials file operations."""
    
    def __init__(self):
        self.credentials_path = os.path.expanduser("~/.aws/credentials")
        self.aws_dir = os.path.dirname(self.credentials_path)
        self._config_cache = None
        self._config_cache_time = 0
        self._config_cache_ttl = 2.0  # Cache for 2 seconds to avoid redundant reads
    
    def _get_config(self, use_cache: bool = True) -> configparser.ConfigParser:
        """Get config parser with optional caching to reduce file I/O."""
        current_time = time.time()
        
        # Use cache if available and recent
        if use_cache and self._config_cache is not None:
            if current_time - self._config_cache_time < self._config_cache_ttl:
                # Check if file hasn't changed
                try:
                    file_mtime = os.path.getmtime(self.credentials_path) if os.path.exists(self.credentials_path) else 0
                    if file_mtime <= self._config_cache_time:
                        return self._config_cache
                except OSError:
                    pass
        
        # Read fresh config
        config = configparser.ConfigParser()
        if os.path.exists(self.credentials_path):
            config.read(self.credentials_path)
        
        # Update cache
        if use_cache:
            self._config_cache = config
            self._config_cache_time = current_time
        
        return config
    
    def _secure_file_permissions(self, file_path: str) -> None:
        """Ensure file has strict 0600 permissions (read/write by owner only)."""
        try:
            if os.path.exists(file_path):
                os.chmod(file_path, 0o600)
        except (OSError, NotImplementedError):
            pass

    def _atomic_write_config(self, config: configparser.ConfigParser) -> None:
        """Atomically write configuration to the credentials file to avoid corruption."""
        os.makedirs(self.aws_dir, mode=0o700, exist_ok=True)
        try:
            os.chmod(self.aws_dir, 0o700)
        except (OSError, NotImplementedError):
            pass

        temp_path = f"{self.credentials_path}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
        try:
            with open(temp_path, "w") as configfile:
                config.write(configfile)
            
            self._secure_file_permissions(temp_path)
            os.replace(temp_path, self.credentials_path)
            self._secure_file_permissions(self.credentials_path)
            
            # Invalidate cache after write
            self._config_cache = None
            self._config_cache_time = 0
            logger.debug(f"Atomically updated AWS credentials file at {self.credentials_path}")
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            logger.error(f"Failed to atomically write credentials file: {e}")
            raise

    def write_credentials(self, profile_names: List[str], creds: Dict[str, str], region: str) -> None:
        """Write AWS credentials to the credentials file for specified profiles."""
        config = self._get_config(use_cache=False)  # Don't use cache when writing

        for profile_name in profile_names:
            if profile_name not in config.sections():
                config.add_section(profile_name)
                
            # Update credentials
            config[profile_name]["aws_access_key_id"] = creds["accessKeyId"]
            config[profile_name]["aws_secret_access_key"] = creds["secretAccessKey"]
            config[profile_name]["aws_session_token"] = creds["sessionToken"]
            config[profile_name]["region"] = region

        self._atomic_write_config(config)

    def get_existing_profiles(self) -> Set[str]:
        """Get list of existing profile names from credentials file."""
        if not os.path.exists(self.credentials_path):
            return set()
        
        try:
            config = self._get_config()  # Use cached config if available
            return set(config.sections())
        except Exception as e:
            logger.warning(f"Failed to read existing profiles: {e}")
            return set()

    def get_unmasked_profile_credentials(self, profile_name: str) -> Optional[Dict[str, str]]:
        """Get raw (unmasked) credentials for a profile, suitable for environment variable export."""
        if not os.path.exists(self.credentials_path):
            return None
        
        try:
            config = self._get_config()
            if profile_name in config.sections():
                return dict(config[profile_name])
            return None
        except Exception as e:
            logger.error(f"Failed to read profile {profile_name}: {e}")
            return None

    def get_profile_info(self, profile_name: str) -> Optional[Dict[str, str]]:
        """Get information about a specific profile."""
        raw_data = self.get_unmasked_profile_credentials(profile_name)
        if raw_data is None:
            return None
        
        masked_data = raw_data.copy()
        if 'aws_access_key_id' in masked_data:
            masked_data['aws_access_key_id'] = masked_data['aws_access_key_id'][:8] + '...'
        if 'aws_secret_access_key' in masked_data:
            masked_data['aws_secret_access_key'] = '***masked***'
        if 'aws_session_token' in masked_data:
            masked_data['aws_session_token'] = masked_data['aws_session_token'][:20] + '...'
        return masked_data

    def backup_credentials(self) -> bool:
        """Create a backup of the current credentials file."""
        if not os.path.exists(self.credentials_path):
            return True
        
        backup_path = f"{self.credentials_path}.backup"
        try:
            shutil.copy2(self.credentials_path, backup_path)
            self._secure_file_permissions(backup_path)
            logger.debug(f"Backup created at {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    def set_default_profile(self, source_profile: str) -> bool:
        """Copy a profile's credentials to the default profile."""
        if not os.path.exists(self.credentials_path):
            logger.error("No credentials file found")
            return False
        
        try:
            config = self._get_config(use_cache=False)  # Don't use cache when modifying
            
            if source_profile not in config.sections():
                logger.error(f"Profile '{source_profile}' not found")
                return False
            
            # Create backup first
            if not self.backup_credentials():
                logger.warning("Could not create backup, proceeding anyway")
            
            # Copy source profile to default
            if 'default' not in config.sections():
                config.add_section('default')
            
            for key, value in config[source_profile].items():
                config['default'][key] = value
            
            self._atomic_write_config(config)
            logger.debug(f"Set '{source_profile}' as default profile")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set default profile: {e}")
            return False

    def get_default_profile_name(self) -> Optional[str]:
        """Determine which profile is currently set as default by comparing credentials.
        
        Returns:
            The name of the profile that matches the default profile credentials, or None
        """
        if not os.path.exists(self.credentials_path):
            return None
        
        try:
            config = self._get_config()  # Use cached config if available
            
            # If no default profile exists, return None
            if 'default' not in config.sections():
                return None
            
            default_creds = dict(config['default'])
            default_access_key = default_creds.get('aws_access_key_id')
            default_token = default_creds.get('aws_session_token', '')
            
            if not default_access_key:
                return None
            
            # Compare default profile with other profiles
            for section_name in config.sections():
                if section_name == 'default':
                    continue
                
                profile_creds = dict(config[section_name])
                profile_access_key = profile_creds.get('aws_access_key_id')
                profile_token = profile_creds.get('aws_session_token', '')
                
                # Match if access key and token match (or if both are empty strings)
                if (profile_access_key == default_access_key and 
                    profile_token == default_token):
                    return section_name
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to determine default profile: {e}")
            return None

    def delete_profile(self, profile_name: str) -> bool:
        """Delete a specific profile from credentials file."""
        if profile_name == 'default':
            logger.error("Cannot delete default profile")
            return False
        
        if not os.path.exists(self.credentials_path):
            logger.error("No credentials file found")
            return False
        
        try:
            config = self._get_config(use_cache=False)  # Don't use cache when modifying
            
            if profile_name not in config.sections():
                logger.warning(f"Profile '{profile_name}' not found")
                return True
            
            # Create backup first
            if not self.backup_credentials():
                logger.warning("Could not create backup, proceeding anyway")
            
            config.remove_section(profile_name)
            self._atomic_write_config(config)
            
            logger.debug(f"Deleted profile '{profile_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete profile: {e}")
            return False
