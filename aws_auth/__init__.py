"""
AWS SSO Authentication Package

A modular Python package for AWS SSO authentication and credential management.
"""

from .auth_manager import AuthManager
from .config import Config
from .token_manager import TokenManager
from .local_browser_manager import LocalBrowserManager
from .sso_client import SSOClient
from .credentials_manager import CredentialsManager
from .user_interface import UserInterface
from .profile_manager import ProfileManager
from .ec2_manager import EC2Manager
from .eks_manager import EKSManager

__version__ = "1.0.1"
__author__ = "N0mansky"

__all__ = [
    "AuthManager",
    "Config", 
    "TokenManager",
    "LocalBrowserManager",
    "SSOClient",
    "CredentialsManager",
    "UserInterface",
    "ProfileManager",
    "EC2Manager",
    "EKSManager",
]
