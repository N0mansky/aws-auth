"""Tests for aws_auth.auth_manager and offer_resource_exploration."""

import unittest
from unittest.mock import patch, MagicMock
from aws_auth.auth_manager import AuthManager, AuthResult
from aws_auth.cli import offer_resource_exploration


class TestOfferResourceExploration(unittest.TestCase):

    @patch("builtins.input", return_value="3")
    @patch("aws_auth.cli.EC2Manager")
    @patch("aws_auth.cli.EKSManager")
    def test_choice_3_skips(self, mock_eks, mock_ec2, mock_input):
        offer_resource_exploration("test-profile", "us-east-1")
        mock_ec2.assert_not_called()
        mock_eks.assert_not_called()

    @patch("builtins.input", return_value="1")
    @patch("aws_auth.cli.EKSManager")
    @patch("aws_auth.cli.UserInterface")
    def test_choice_1_lists_eks(self, mock_ui_cls, mock_eks_cls, mock_input):
        mock_eks = MagicMock()
        mock_eks_cls.return_value = mock_eks
        mock_eks.list_clusters.return_value = []
        offer_resource_exploration("test-profile", "us-east-1")
        mock_eks.list_clusters.assert_called_once_with("us-east-1")

    @patch("builtins.input", return_value="")
    @patch("aws_auth.cli.EKSManager")
    @patch("aws_auth.cli.UserInterface")
    def test_default_choice_lists_eks(self, mock_ui_cls, mock_eks_cls, mock_input):
        mock_eks = MagicMock()
        mock_eks_cls.return_value = mock_eks
        mock_eks.list_clusters.return_value = []
        offer_resource_exploration("test-profile", "us-east-1")
        mock_eks.list_clusters.assert_called_once_with("us-east-1")

    @patch("builtins.input", return_value="2")
    @patch("aws_auth.cli.EC2Manager")
    @patch("aws_auth.cli.UserInterface")
    def test_choice_2_lists_ec2(self, mock_ui_cls, mock_ec2_cls, mock_input):
        mock_ec2 = MagicMock()
        mock_ec2_cls.return_value = mock_ec2
        mock_ec2.list_instances.return_value = []
        offer_resource_exploration("test-profile", "us-east-1")
        mock_ec2.list_instances.assert_called_once_with("us-east-1")


class TestAuthManager(unittest.TestCase):
    @patch("aws_auth.auth_manager.Config")
    def setUp(self, mock_config_cls):
        mock_config = MagicMock()
        mock_config.validate.return_value = True
        mock_config_cls.return_value = mock_config
        with patch("aws_auth.auth_manager.TokenManager"), \
             patch("aws_auth.auth_manager.LocalBrowserManager"), \
             patch("aws_auth.auth_manager.SSOClient"), \
             patch("aws_auth.auth_manager.CredentialsManager"), \
             patch("aws_auth.auth_manager.UserInterface"):
            self.manager = AuthManager(config=mock_config)

    def test_auth_manager_initialization(self):
        self.assertIsNotNone(self.manager.token_manager)
        self.assertIsNotNone(self.manager.sso_client)


class TestSSOClientTokenLogging(unittest.TestCase):
    """Tests for exception handling and log levels in SSOClient.create_token."""

    def setUp(self):
        with patch("aws_auth.sso_client.boto3.client"):
            from aws_auth.sso_client import SSOClient
            mock_config = MagicMock()
            mock_config.SSO_REGION = "us-east-1"
            mock_config.SSO_START_URL = "https://portal.awsapps.com/start"
            self.client = SSOClient(config=mock_config)

    @patch("aws_auth.sso_client.logger")
    def test_authorization_pending_logs_debug_not_error(self, mock_logger):
        class AuthorizationPendingException(Exception):
            pass

        self.client.oidc_client.create_token.side_effect = AuthorizationPendingException("Authorization is still pending")
        
        with self.assertRaises(AuthorizationPendingException):
            self.client.create_device_token("client_id", "client_secret", "code_123")

        # Must not log "Failed to create token" as an error for AuthorizationPendingException
        for call in mock_logger.error.call_args_list:
            args, _ = call
            self.assertNotIn("Failed to create token with urn:ietf:params:oauth:grant-type:device_code", args[0])

        mock_logger.debug.assert_called()

    @patch("aws_auth.sso_client.logger")
    def test_slow_down_logs_debug_not_error(self, mock_logger):
        class SlowDownException(Exception):
            pass

        self.client.oidc_client.create_token.side_effect = SlowDownException("Too many requests")
        
        with self.assertRaises(SlowDownException):
            self.client.create_device_token("client_id", "client_secret", "code_123")

        for call in mock_logger.error.call_args_list:
            args, _ = call
            self.assertNotIn("Failed to create token with urn:ietf:params:oauth:grant-type:device_code", args[0])

        mock_logger.debug.assert_called()

    @patch("aws_auth.sso_client.logger")
    def test_other_exceptions_logged_as_error(self, mock_logger):
        class InvalidRequestException(Exception):
            pass

        self.client.oidc_client.create_token.side_effect = InvalidRequestException("Invalid request parameter")
        
        with self.assertRaises(InvalidRequestException):
            self.client.create_device_token("client_id", "client_secret", "code_123")

        mock_logger.error.assert_called()


class TestAuthManagerDevicePolling(unittest.TestCase):
    """Tests for device authorization polling and timer output in AuthManager."""

    def setUp(self):
        mock_config = MagicMock()
        mock_config.validate.return_value = True
        mock_config.SESSION_DURATION_SECONDS = 3600
        mock_config.MAX_POLLING_SECONDS = 120
        with patch("aws_auth.auth_manager.TokenManager"), \
             patch("aws_auth.auth_manager.LocalBrowserManager"), \
             patch("aws_auth.auth_manager.SSOClient"), \
             patch("aws_auth.auth_manager.CredentialsManager"), \
             patch("aws_auth.auth_manager.UserInterface"):
            self.manager = AuthManager(config=mock_config)

    @patch("sys.stderr.write")
    @patch("sys.stderr.flush")
    @patch("sys.stderr.isatty", return_value=True)
    @patch("time.sleep")
    def test_polling_in_place_timer_and_success(self, mock_sleep, mock_isatty, mock_flush, mock_stderr_write):
        class AuthorizationPendingException(Exception):
            pass

        self.manager.sso_client.oidc_client.exceptions.AuthorizationPendingException = AuthorizationPendingException
        self.manager.sso_client.register_client.return_value = ("client-123", "secret-456")
        self.manager.sso_client.start_device_authorization.return_value = {
            "verificationUriComplete": "https://portal.awsapps.com/start/#/device?user_code=ABCD",
            "deviceCode": "device-code-xyz",
            "userCode": "ABCD",
            "expiresIn": 300,
            "interval": 1,
        }

        # First 2 calls pending, 3rd call succeeds
        self.manager.sso_client.create_device_token.side_effect = [
            AuthorizationPendingException("Pending"),
            AuthorizationPendingException("Pending"),
            {"accessToken": "test-access-token", "expiresIn": 3600, "refreshToken": "test-refresh-token"}
        ]

        token = self.manager._perform_sso_login()
        self.assertEqual(token, "test-access-token")

        # Verify stderr in-place writes occurred with carriage return
        written_texts = [call[0][0] for call in mock_stderr_write.call_args_list]
        r_updates = [text for text in written_texts if "\r" in text and "Polling for device authorization token" in text]
        self.assertGreaterEqual(len(r_updates), 1)

        # Verify clean newline was written upon loop completion
        self.assertIn("\n", written_texts)

    @patch("sys.stderr.isatty", return_value=False)
    @patch("time.sleep")
    def test_polling_handles_slowdown_exception(self, mock_sleep, mock_isatty):
        class SlowDownException(Exception):
            pass

        self.manager.sso_client.oidc_client.exceptions.SlowDownException = SlowDownException
        self.manager.sso_client.register_client.return_value = ("client-123", "secret-456")
        self.manager.sso_client.start_device_authorization.return_value = {
            "verificationUriComplete": "https://portal.awsapps.com/start/#/device?user_code=ABCD",
            "deviceCode": "device-code-xyz",
            "userCode": "ABCD",
            "expiresIn": 300,
            "interval": 1,
        }

        self.manager.sso_client.create_device_token.side_effect = [
            SlowDownException("Rate limited"),
            {"accessToken": "test-access-token", "expiresIn": 3600}
        ]

        token = self.manager._perform_sso_login()
        self.assertEqual(token, "test-access-token")
        # Sleep called with interval + 5 = 6
        mock_sleep.assert_called_with(6)

    @patch("sys.stderr.isatty", return_value=False)
    @patch("time.sleep")
    def test_polling_handles_expired_token(self, mock_sleep, mock_isatty):
        class ExpiredTokenException(Exception):
            pass

        self.manager.sso_client.register_client.return_value = ("client-123", "secret-456")
        self.manager.sso_client.start_device_authorization.return_value = {
            "verificationUriComplete": "https://portal.awsapps.com/start/#/device?user_code=ABCD",
            "deviceCode": "device-code-xyz",
            "userCode": "ABCD",
            "expiresIn": 300,
            "interval": 1,
        }

        self.manager.sso_client.create_device_token.side_effect = ExpiredTokenException("Expired")

        with self.assertRaises(RuntimeError) as ctx:
            self.manager._perform_sso_login()
        self.assertIn("Login timed out", str(ctx.exception))




if __name__ == "__main__":
    unittest.main()
