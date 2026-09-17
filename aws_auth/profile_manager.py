"""Profile management functionality for AWS credentials."""

import logging
from typing import Dict, List, Optional
from botocore.exceptions import ClientError

from .credentials_manager import CredentialsManager
from .user_interface import UserInterface
from .caller_identity import display_caller_identity, get_caller_identity
from .auth_manager import AuthManager

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages AWS profile operations including listing, setting default, and deletion."""
    
    def __init__(self):
        self.credentials_manager = CredentialsManager()
        self.ui = UserInterface()
    
    def list_profiles(self) -> None:
        """List all existing AWS profiles with their information."""
        existing_profiles = self.credentials_manager.get_existing_profiles()
        
        if not existing_profiles:
            print("No AWS profiles found.")
            return
        
        profiles_info = {}
        for profile_name in existing_profiles:
            profile_info = self.credentials_manager.get_profile_info(profile_name)
            profiles_info[profile_name] = profile_info
        
        self.ui.display_profiles(profiles_info)
    
    def switch_profile(self, set_as_default: bool = False) -> Optional[str]:
        """Quickly switch to an existing profile without re-authenticating.
        
        Args:
            set_as_default: If True, also sets the selected profile as default in credentials file.
                           If False (default), persists active profile to ~/.aws-auth/current_profile.
        
        Returns:
            The selected profile name, or None if cancelled
        """
        existing_profiles = list(self.credentials_manager.get_existing_profiles())
        
        if not existing_profiles:
            print("No AWS profiles found. Please add a profile first with: aws-auth.py")
            return None
        
        # Determine which profile is currently active
        active_profile = self.credentials_manager.get_active_profile()
        
        # Show profiles in table format (filter out 'default' and show indicator)
        profiles_info = {}
        # Filter out 'default' from the list
        filtered_profiles = [p for p in existing_profiles if p != 'default']
        for profile_name in filtered_profiles:
            profile_info = self.credentials_manager.get_profile_info(profile_name)
            profiles_info[profile_name] = profile_info
        
        self.ui.display_profiles_table(profiles_info, active_profile=active_profile)
        
        # Let user select (from filtered list, not including 'default')
        selected_profile = self.ui.select_profile_to_use(filtered_profiles, active_profile=active_profile)
        
        if selected_profile:
            # Check if credentials are expired before switching
            credentials_expired = False
            
            # Try to get caller identity to check if credentials are valid
            try:
                import boto3
                if selected_profile and selected_profile != 'default':
                    session = boto3.Session(profile_name=selected_profile)
                else:
                    session = boto3.Session()
                sts_client = session.client('sts')
                sts_client.get_caller_identity()
                # If we get here, credentials are valid
                credentials_expired = False
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ExpiredToken':
                    credentials_expired = True
                else:
                    # Other error - credentials might be invalid but not necessarily expired
                    credentials_expired = False
            except Exception:
                # Can't determine - assume not expired and let it fail later
                credentials_expired = False
            
            # If credentials are expired, automatically re-authenticate
            if credentials_expired:
                print(f"\n⚠️  Credentials for profile '{selected_profile}' are expired.")
                print(f"🔐 Automatically re-authenticating...")
                print("   Please select the same account-role combination to update this profile.")
                try:
                    auth_manager = AuthManager()
                    auth_result = auth_manager.assume_role_via_sso(set_as_default=set_as_default)
                    target_to_use = selected_profile
                    if auth_result.profile_names:
                        target_to_use = auth_result.profile_names[0]
                    self.credentials_manager.set_current_profile(target_to_use)
                    if set_as_default:
                        self.credentials_manager.set_default_profile(target_to_use)
                    display_caller_identity(profile_name=target_to_use)
                    return target_to_use
                except Exception as e:
                    logger.error(f"Re-authentication failed: {e}")
                    print(f"❌ Re-authentication failed: {e}")
                    return None
            
            # Credentials are valid, proceed with switch
            self.credentials_manager.set_current_profile(selected_profile)
            
            if set_as_default:
                if self.credentials_manager.set_default_profile(selected_profile):
                    print(f"\n✅ Switched to profile: {selected_profile} (and set as default)")
                    # Show caller identity for the selected profile
                    display_caller_identity(profile_name=selected_profile)
                    return selected_profile
                else:
                    print(f"\n❌ Failed to set '{selected_profile}' as default profile.")
                    return None
            else:
                print(f"\n✅ Switched active profile to: {selected_profile}")
                # Show caller identity for the selected profile
                display_caller_identity(profile_name=selected_profile)
                return selected_profile
        
        return None
    
    def set_default_profile(self) -> Optional[bool]:
        """Interactive selection to set a profile as default."""
        existing_profiles = list(self.credentials_manager.get_existing_profiles())
        
        if not existing_profiles:
            print("No AWS profiles found. Please add a profile first.")
            return False
        
        selected_profile = self.ui.select_profile_for_default(existing_profiles)
        if selected_profile:
            success = self.credentials_manager.set_default_profile(selected_profile)
            if success:
                self.credentials_manager.set_current_profile(selected_profile)
            return success
        
        return None
    
    def delete_profile(self) -> Optional[bool]:
        """Interactive selection to delete a profile."""
        existing_profiles = list(self.credentials_manager.get_existing_profiles())
        
        if not existing_profiles:
            print("No AWS profiles found.")
            return False
        
        selected_profile = self.ui.select_profile_for_deletion(existing_profiles)
        if selected_profile:
            return self.credentials_manager.delete_profile(selected_profile)
        
        return None
    
    def get_existing_profiles_list(self) -> List[str]:
        """Get list of existing profile names."""
        return list(self.credentials_manager.get_existing_profiles())
    
    def run_interactive_menu(self) -> None:
        """Run interactive profile management menu."""
        while True:
            choice = self.ui.show_profile_menu()
            
            if choice == '1':
                print("Returning to main authentication flow to add new profile...")
                break
            elif choice == '2':
                self.list_profiles()
            elif choice == '3':
                res = self.set_default_profile()
                if res is True:
                    print("Default profile updated successfully!")
                elif res is False:
                    print("Failed to update default profile.")
            elif choice == '4':
                res = self.delete_profile()
                if res is True:
                    print("Profile deleted successfully!")
                elif res is False:
                    print("Failed to delete profile.")
            elif choice == '5':
                print("Exiting profile management.")
                break
            
            input("\nPress Enter to continue...")
