"""Get AWS caller identity to verify current user/account."""

import boto3
import logging
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


def get_caller_identity(profile_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get AWS caller identity for the specified profile.
    
    Args:
        profile_name: AWS profile name (None for default profile)
        
    Returns:
        Dict with 'UserId', 'Account', 'Arn', or None if failed
    """
    try:
        if profile_name and profile_name != 'default':
            session = boto3.Session(profile_name=profile_name)
        else:
            session = boto3.Session()
        
        sts_client = session.client('sts')
        response = sts_client.get_caller_identity()
        
        return {
            'UserId': response.get('UserId'),
            'Account': response.get('Account'),
            'Arn': response.get('Arn')
        }
    except NoCredentialsError:
        logger.warning("No AWS credentials found")
        return None
    except ClientError as e:
        logger.warning(f"Failed to get caller identity: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error getting caller identity: {e}")
        return None


def display_caller_identity(profile_name: Optional[str] = None) -> bool:
    """Display AWS caller identity in a nice format.
    
    Args:
        profile_name: AWS profile name (None for default profile)
        
    Returns:
        True if successful, False otherwise
    """
    identity = get_caller_identity(profile_name)
    
    if not identity:
        print("❌ Could not retrieve AWS caller identity")
        print("   Credentials may be expired or invalid")
        return False
    
    print("\n" + "=" * 70)
    print("👤 Current AWS Identity")
    print("=" * 70)
    print(f"Account ID:  {identity.get('Account', 'N/A')}")
    print(f"User ID:     {identity.get('UserId', 'N/A')}")
    
    arn = identity.get('Arn', '')
    if arn:
        # Parse ARN to extract readable info
        # Format: arn:aws:sts::ACCOUNT:assumed-role/ROLE/SESSION
        # or: arn:aws:iam::ACCOUNT:user/USERNAME
        if ':assumed-role/' in arn:
            # Extract role name from ARN
            # Example: arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_AdministratorAccess_d39bab190ecb5ec0/user@example.com
            role_part = arn.split(':assumed-role/')[1]
            parts = role_part.split('/')
            if len(parts) >= 1:
                role_name = parts[0]
                # Clean up SSO role names (remove AWSReservedSSO_ prefix and hash)
                if role_name.startswith('AWSReservedSSO_'):
                    # Extract the readable part: AWSReservedSSO_AdministratorAccess_d39bab190ecb5ec0
                    # -> AdministratorAccess
                    role_clean = role_name.replace('AWSReservedSSO_', '')
                    # Remove the hash at the end (last part after last underscore)
                    # Hash is typically 16 hex characters
                    if '_' in role_clean:
                        role_parts = role_clean.rsplit('_', 1)
                        if len(role_parts) == 2 and len(role_parts[1]) == 16:
                            role_clean = role_parts[0]
                    role_name = role_clean
                
                session_name = parts[1] if len(parts) > 1 else 'N/A'
                print(f"Role:        {role_name}")
                if session_name != 'N/A':
                    print(f"Session:     {session_name}")
        elif '/user/' in arn:
            parts = arn.split('/')
            if len(parts) >= 2:
                username = parts[1]
                print(f"User:        {username}")
        
        print(f"ARN:         {arn}")
    
    print("=" * 70)
    return True

