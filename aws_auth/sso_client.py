"""AWS SSO client operations."""

import logging
import boto3
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from .config import Config
from .token_manager import TokenManager

logger = logging.getLogger(__name__)


class SSOClient:
    """Manages AWS SSO API operations."""
    
    def __init__(self, config: Config):
        self.config = config
        self.sso_client = boto3.client("sso", region_name=config.SSO_REGION)
        self.oidc_client = boto3.client("sso-oidc", region_name=config.SSO_REGION)
    
    def _list_paginated(self, method_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Paginate through SSO API responses to get all results."""
        results = []
        next_token = None
        
        while True:
            current_params = params.copy()
            if next_token:
                current_params["nextToken"] = next_token
                
            try:
                response = getattr(self.sso_client, method_name)(**current_params)
                # Extract the appropriate list from response
                batch_results = (response.get("accountList") or 
                               response.get("roleList") or 
                               [])
                results.extend(batch_results)
                
                next_token = response.get("nextToken")
                if not next_token:
                    break
            except Exception as e:
                logger.error(f"Error during pagination: {e}")
                raise
                
        return results
    
    def list_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """List all available AWS accounts."""
        return self._list_paginated("list_accounts", {"accessToken": access_token})
    
    def list_account_roles(self, access_token: str, account_id: str) -> List[Dict[str, Any]]:
        """List all available roles for a specific account."""
        return self._list_paginated(
            "list_account_roles",
            {"accessToken": access_token, "accountId": account_id}
        )
    
    def get_role_credentials(self, access_token: str, account_id: str, role_name: str) -> Dict[str, str]:
        """Get temporary credentials for a specific role."""
        try:
            response = self.sso_client.get_role_credentials(
                roleName=role_name,
                accountId=account_id,
                accessToken=access_token,
            )
            return response["roleCredentials"]
        except Exception as e:
            logger.error(f"Failed to get role credentials: {e}")
            raise
    
    def register_client(self, token_manager: TokenManager) -> Tuple[str, str]:
        """Register a new OIDC client or load cached one."""
        client_id, client_secret = token_manager.load_registered_client()
        if not client_id:
            logger.info("Registering new OIDC client...")
            
            # Prepare registration parameters according to AWS documentation
            register_params = {
                "clientName": self.config.CLIENT_NAME,
                "clientType": self.config.CLIENT_TYPE,
            }
            
            # Add optional parameters if configured
            if self.config.CLIENT_SCOPES:
                register_params["scopes"] = self.config.CLIENT_SCOPES
            if self.config.CLIENT_GRANT_TYPES:
                register_params["grantTypes"] = self.config.CLIENT_GRANT_TYPES
                
            try:
                register_response = self.oidc_client.register_client(**register_params)
                
                # Save the registration response
                client_id = register_response["clientId"]
                client_secret = register_response["clientSecret"]
                
                # Save all the response data for future reference
                token_manager.save_registered_client(
                    client_id=client_id,
                    client_secret=client_secret,
                    client_id_issued_at=register_response.get("clientIdIssuedAt"),
                    client_secret_expires_at=register_response.get("clientSecretExpiresAt"),
                    token_endpoint=register_response.get("tokenEndpoint")
                )
                
                logger.info(f"Registered client ID: {client_id}")
                if register_response.get("clientSecretExpiresAt"):
                    expiry_time = datetime.fromtimestamp(register_response["clientSecretExpiresAt"])
                    logger.info(f"Client secret expires at: {expiry_time}")
            except Exception as e:
                logger.error(f"Failed to register OIDC client: {e}")
                self._handle_register_client_exceptions(e)
                raise
        else:
            logger.info(f"Using cached OIDC client ID: {client_id}")
        
        return client_id, client_secret
    
    def start_device_authorization(self, client_id: str, client_secret: str) -> Dict[str, Any]:
        """Start device authorization flow."""
        return self.oidc_client.start_device_authorization(
            clientId=client_id, 
            clientSecret=client_secret, 
            startUrl=self.config.SSO_START_URL
        )
    
    def create_token(self, client_id: str, client_secret: str, grant_type: str, 
                    device_code: Optional[str] = None, 
                    refresh_token: Optional[str] = None, scope: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create access and refresh tokens for different OAuth grant types.
        
        Args:
            client_id: The unique identifier for the client
            client_secret: Secret string generated for the client
            grant_type: OAuth grant type (device_code, refresh_token)
            device_code: Used for device code grant type
            refresh_token: Used for refresh token grant type
            scope: List of scopes (optional)
            
        Returns:
            Dict containing accessToken, tokenType, expiresIn, refreshToken, idToken
        """
        # Prepare required parameters
        token_params = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "grantType": grant_type,
        }
        
        # Add optional parameters based on grant type
        if grant_type == "urn:ietf:params:oauth:grant-type:device_code":
            if not device_code:
                raise ValueError("device_code is required for device code grant type")
            token_params["deviceCode"] = device_code
            
        elif grant_type == "refresh_token":
            if not refresh_token:
                raise ValueError("refresh_token is required for refresh token grant type")
            token_params["refreshToken"] = refresh_token
        else:
            raise ValueError(f"Unsupported grant type: {grant_type}")
            
        # Add optional scope if provided
        if scope:
            token_params["scope"] = scope
            
        try:
            response = self.oidc_client.create_token(**token_params)
            logger.info(f"Successfully created token using {grant_type} grant type")
            
            if response.get("refreshToken"):
                logger.info("Refresh token received and will be cached")
                
            return response
            
        except Exception as e:
            logger.error(f"Failed to create token with {grant_type}: {e}")
            self._handle_create_token_exceptions(e)
            raise
    
    def create_device_token(self, client_id: str, client_secret: str, device_code: str) -> Dict[str, Any]:
        """Create access token from device code (convenience method for backward compatibility)."""
        return self.create_token(
            client_id=client_id,
            client_secret=client_secret,
            grant_type="urn:ietf:params:oauth:grant-type:device_code",
            device_code=device_code
        )
    
    def refresh_access_token(self, client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token (convenience method)."""
        return self.create_token(
            client_id=client_id,
            client_secret=client_secret,
            grant_type="refresh_token",
            refresh_token=refresh_token
        )
    
    def _handle_register_client_exceptions(self, exception: Exception) -> None:
        """Handle specific exceptions from register_client according to AWS documentation."""
        exception_name = exception.__class__.__name__
        
        if "InvalidRequestException" in exception_name:
            logger.error("Invalid request: The request contains invalid parameters")
        elif "InvalidScopeException" in exception_name:
            logger.error("Invalid scope: One or more scopes are invalid")
        elif "InvalidClientMetadataException" in exception_name:
            logger.error("Invalid client metadata: The client metadata is invalid")
        elif "InternalServerException" in exception_name:
            logger.error("Internal server error: AWS service encountered an error")
        elif "InvalidRedirectUriException" in exception_name:
            logger.error("Invalid redirect URI: One or more redirect URIs are invalid")
        elif "UnsupportedGrantTypeException" in exception_name:
            logger.error("Unsupported grant type: One or more grant types are not supported")
        elif "SlowDownException" in exception_name:
            logger.error("Too many requests: Client is making requests too frequently")
        else:
            logger.error(f"Unexpected error during client registration: {exception}")
    
    def _handle_create_token_exceptions(self, exception: Exception) -> None:
        """Handle specific exceptions from create_token according to AWS documentation."""
        exception_name = exception.__class__.__name__
        
        if "InvalidRequestException" in exception_name:
            logger.error("Invalid request: The request contains invalid parameters")
        elif "InvalidClientException" in exception_name:
            logger.error("Invalid client: The client identifier is invalid")
        elif "InvalidGrantException" in exception_name:
            logger.error("Invalid grant: The provided authorization grant is invalid")
        elif "UnauthorizedClientException" in exception_name:
            logger.error("Unauthorized client: The client is not authorized to request a token")
        elif "UnsupportedGrantTypeException" in exception_name:
            logger.error("Unsupported grant type: The grant type is not supported")
        elif "InvalidScopeException" in exception_name:
            logger.error("Invalid scope: The requested scope is invalid")
        elif "AuthorizationPendingException" in exception_name:
            logger.debug("Authorization pending: The authorization request is still pending")
        elif "SlowDownException" in exception_name:
            logger.error("Too many requests: Client is making requests too frequently")
        elif "AccessDeniedException" in exception_name:
            logger.error("Access denied: The client does not have permission to perform this action")
        elif "ExpiredTokenException" in exception_name:
            logger.error("Expired token: The provided token has expired")
        elif "InternalServerException" in exception_name:
            logger.error("Internal server error: AWS service encountered an error")
        else:
            logger.error(f"Unexpected error during token creation: {exception}")
