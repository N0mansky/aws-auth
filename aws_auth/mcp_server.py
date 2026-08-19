"""Model Context Protocol (MCP) Server for AWS SSO Authentication and Context Switching."""

import os
import logging
from typing import Optional, Dict, Any, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from mcp.server.mcpserver import MCPServer

from aws_auth.credentials_manager import CredentialsManager
from aws_auth.caller_identity import get_caller_identity
from aws_auth.ec2_manager import EC2Manager
from aws_auth.eks_manager import EKSManager
from aws_auth.auth_manager import AuthManager
from aws_auth.config import Config

logger = logging.getLogger(__name__)

# Initialize MCP Server
mcp_server = MCPServer("aws-auth")


@mcp_server.tool()
def aws_list_profiles() -> Dict[str, Any]:
    """List all available local AWS profiles, current active default profile, and configured regions."""
    cm = CredentialsManager()
    existing_profiles = list(cm.get_existing_profiles())
    default_profile = cm.get_default_profile_name()
    
    profiles_info = {}
    for profile in existing_profiles:
        info = cm.get_profile_info(profile)
        profiles_info[profile] = {
            "region": info.get("region", "us-east-1") if info else "us-east-1",
            "is_default": (profile == default_profile or profile == "default"),
            "has_credentials": bool(info and "aws_access_key_id" in info)
        }
    
    return {
        "success": True,
        "default_profile": default_profile or "default",
        "profiles": profiles_info
    }


@mcp_server.tool()
def aws_switch_profile(profile_name: str) -> Dict[str, Any]:
    """Switch the default AWS credentials profile in ~/.aws/credentials to a specific profile name.
    
    Args:
        profile_name: Name of the AWS profile to set as default (e.g. 'dev', 'prod', 'qa')
    """
    cm = CredentialsManager()
    existing_profiles = cm.get_existing_profiles()
    if profile_name not in existing_profiles:
        return {
            "success": False,
            "error": f"Profile '{profile_name}' not found. Available profiles: {list(existing_profiles)}"
        }
    
    if cm.set_default_profile(profile_name):
        identity = get_caller_identity(profile_name=None)
        return {
            "success": True,
            "message": f"Successfully switched default profile to '{profile_name}'",
            "active_profile": profile_name,
            "identity": identity
        }
    else:
        return {
            "success": False,
            "error": f"Failed to set '{profile_name}' as default profile."
        }


@mcp_server.tool()
def aws_get_caller_identity(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """Get current AWS caller identity (Account ID, IAM Role/User ARN, User ID) using STS.
    
    Args:
        profile_name: Optional profile name to check. If omitted, checks the default profile.
    """
    identity = get_caller_identity(profile_name=profile_name)
    if identity:
        return {
            "success": True,
            "profile": profile_name or "default",
            "identity": identity
        }
    else:
        return {
            "success": False,
            "profile": profile_name or "default",
            "error": "Could not retrieve caller identity. Credentials may be missing, invalid, or expired."
        }


@mcp_server.tool()
def aws_get_session_env(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """Get raw AWS session environment variables (AccessKey, SecretKey, SessionToken, Region) for isolated subprocess execution.
    
    Args:
        profile_name: AWS profile name (defaults to 'default')
    """
    target_profile = profile_name or "default"
    cm = CredentialsManager()
    creds = cm.get_unmasked_profile_credentials(target_profile)
    
    if not creds:
        return {
            "success": False,
            "error": f"Profile '{target_profile}' not found or has no credentials."
        }
    
    env_vars = {
        "AWS_ACCESS_KEY_ID": creds.get("aws_access_key_id", ""),
        "AWS_SECRET_ACCESS_KEY": creds.get("aws_secret_access_key", ""),
        "AWS_SESSION_TOKEN": creds.get("aws_session_token", ""),
        "AWS_DEFAULT_REGION": creds.get("region", "us-east-1"),
        "AWS_REGION": creds.get("region", "us-east-1"),
        "AWS_PROFILE": target_profile
    }
    
    return {
        "success": True,
        "profile": target_profile,
        "env": env_vars
    }


@mcp_server.tool()
def aws_ensure_credentials(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """Check if AWS credentials are valid, and automatically refresh using cached SSO refresh token if expired.
    
    Args:
        profile_name: AWS profile name (defaults to 'default')
    """
    target_profile = profile_name or "default"
    identity = get_caller_identity(profile_name=target_profile)
    
    if identity:
        return {
            "success": True,
            "status": "valid",
            "profile": target_profile,
            "identity": identity
        }
    
    # Attempt automatic token refresh
    try:
        auth_manager = AuthManager()
        refreshed_token = auth_manager._attempt_token_refresh()
        if refreshed_token:
            return {
                "success": True,
                "status": "refreshed",
                "message": "SSO access token successfully refreshed in background."
            }
        else:
            return {
                "success": False,
                "status": "expired_requires_login",
                "message": "SSO token expired and cannot be refreshed automatically. Run 'aws-auth' in terminal to log in via browser."
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed during credential validation / refresh: {str(e)}"
        }


@mcp_server.tool()
def aws_list_ec2_instances(region: str = "us-east-1", profile_name: str = "default") -> Dict[str, Any]:
    """List EC2 instances in a specific AWS region using the specified profile.
    
    Args:
        region: AWS region (e.g. 'us-east-1', 'us-west-2')
        profile_name: AWS profile name to use (default: 'default')
    """
    try:
        ec2_mgr = EC2Manager(profile_name)
        instances = ec2_mgr.list_instances(region)
        return {
            "success": True,
            "region": region,
            "profile": profile_name,
            "count": len(instances),
            "instances": instances
        }
    except Exception as e:
        return {
            "success": False,
            "region": region,
            "profile": profile_name,
            "error": str(e)
        }


@mcp_server.tool()
def aws_list_eks_clusters(region: str = "us-east-1", profile_name: str = "default", update_kubeconfig: bool = False) -> Dict[str, Any]:
    """List EKS clusters in a specific AWS region and optionally configure local ~/.kube/config.
    
    Args:
        region: AWS region (e.g. 'us-east-1', 'us-west-2')
        profile_name: AWS profile name to use (default: 'default')
        update_kubeconfig: If True, automatically configures kubeconfig for found clusters
    """
    try:
        eks_mgr = EKSManager(profile_name)
        clusters = eks_mgr.list_clusters(region)
        
        kubeconfig_results = {}
        if update_kubeconfig and clusters:
            for cluster in clusters:
                c_name = cluster.get("name")
                if cluster.get("status") == "ACTIVE" and c_name:
                    kubeconfig_results[c_name] = eks_mgr.connect_to_cluster(cluster, region)
        
        return {
            "success": True,
            "region": region,
            "profile": profile_name,
            "count": len(clusters),
            "clusters": clusters,
            "kubeconfig_configured": kubeconfig_results if update_kubeconfig else None
        }
    except Exception as e:
        return {
            "success": False,
            "region": region,
            "profile": profile_name,
            "error": str(e)
        }


@mcp_server.tool()
def aws_update_kubeconfig(cluster_name: str, region: str = "us-east-1", profile_name: str = "default") -> Dict[str, Any]:
    """Configure local kubeconfig to connect to a specific EKS cluster.
    
    Args:
        cluster_name: Name of the EKS cluster
        region: AWS region of the cluster
        profile_name: AWS profile name to authenticate with
    """
    try:
        eks_mgr = EKSManager(profile_name)
        cluster_obj = {"name": cluster_name, "status": "ACTIVE"}
        success = eks_mgr.connect_to_cluster(cluster_obj, region)
        return {
            "success": success,
            "cluster": cluster_name,
            "region": region,
            "profile": profile_name,
            "message": f"Successfully configured kubeconfig context for '{cluster_name}'" if success else "Failed to configure kubeconfig"
        }
    except Exception as e:
        return {
            "success": False,
            "cluster": cluster_name,
            "error": str(e)
        }


def main():
    """Run the MCP server over stdio."""
    # Suppress informational logs on stdout so MCP json-rpc protocol is clean
    logging.basicConfig(level=logging.WARNING)
    mcp_server.run(transport='stdio')


if __name__ == "__main__":
    main()
