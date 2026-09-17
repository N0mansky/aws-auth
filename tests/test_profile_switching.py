"""Unit tests for AWS profile switching, current_profile tracking, and AWS_PROFILE support."""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from aws_auth.credentials_manager import CredentialsManager
from aws_auth.profile_manager import ProfileManager
from aws_auth.auth_manager import AuthManager, AuthResult
from aws_auth.cli import create_parser


class TestCredentialsManagerCurrentProfile(unittest.TestCase):
    """Test suite for current_profile operations in CredentialsManager."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cm = CredentialsManager()
        self.cm.credentials_path = os.path.join(self.temp_dir.name, "credentials")
        self.cm.aws_dir = self.temp_dir.name
        self.cm.current_profile_path = os.path.join(self.temp_dir.name, ".aws-auth", "current_profile")
        self.cm.current_profile_dir = os.path.dirname(self.cm.current_profile_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_set_and_get_current_profile(self):
        self.assertIsNone(self.cm.get_current_profile())
        success = self.cm.set_current_profile("staging-admin")
        self.assertTrue(success)
        self.assertEqual(self.cm.get_current_profile(), "staging-admin")

    def test_set_current_profile_empty(self):
        self.assertFalse(self.cm.set_current_profile("   "))
        self.assertIsNone(self.cm.get_current_profile())

    def test_clear_current_profile(self):
        self.cm.set_current_profile("staging-admin")
        self.assertEqual(self.cm.get_current_profile(), "staging-admin")
        self.cm.clear_current_profile()
        self.assertIsNone(self.cm.get_current_profile())

    def test_get_active_profile_priority(self):
        # 1. Environment variable priority
        with patch.dict(os.environ, {"AWS_PROFILE": "env-override"}):
            self.assertEqual(self.cm.get_active_profile(), "env-override")

        # 2. current_profile file when AWS_PROFILE is not set
        with patch.dict(os.environ, {}, clear=True):
            self.cm.set_current_profile("staging-admin")
            self.assertEqual(self.cm.get_active_profile(), "staging-admin")

        # 3. Fallback when neither is set
        with patch.dict(os.environ, {}, clear=True):
            self.cm.clear_current_profile()
            with patch.object(self.cm, "get_default_profile_name", return_value="default-match"):
                self.assertEqual(self.cm.get_active_profile(), "default-match")

    def test_delete_profile_clears_current_profile_if_active(self):
        # Create a dummy credentials file with a section
        self.cm.write_credentials(
            ["dev-profile"],
            {"accessKeyId": "AKIA123", "secretAccessKey": "secret", "sessionToken": "token"},
            "us-east-1"
        )
        self.cm.set_current_profile("dev-profile")
        self.assertEqual(self.cm.get_current_profile(), "dev-profile")

        self.cm.delete_profile("dev-profile")
        self.assertIsNone(self.cm.get_current_profile())

    def test_set_default_profile_syncs_current_profile(self):
        self.cm.write_credentials(
            ["dev-profile"],
            {"accessKeyId": "AKIA123", "secretAccessKey": "secret", "sessionToken": "token"},
            "us-east-1"
        )
        self.cm.set_default_profile("dev-profile")
        self.assertEqual(self.cm.get_current_profile(), "dev-profile")


class TestProfileManagerSwitching(unittest.TestCase):
    """Test suite for ProfileManager switch_profile without mutating default."""

    @patch("boto3.Session")
    @patch("aws_auth.profile_manager.display_caller_identity")
    def test_switch_profile_does_not_set_default_by_default(self, mock_identity, mock_boto):
        # Mock STS caller identity as valid
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts
        mock_boto.return_value = mock_session

        pm = ProfileManager()
        pm.credentials_manager = MagicMock()
        pm.credentials_manager.get_existing_profiles.return_value = {"staging-admin", "default"}
        pm.credentials_manager.get_active_profile.return_value = "staging-admin"
        pm.credentials_manager.get_profile_info.return_value = {
            "aws_access_key_id": "AKIA...",
            "aws_session_token": "token...",
            "region": "us-east-1"
        }
        pm.ui.select_profile_to_use = MagicMock(return_value="staging-admin")

        result = pm.switch_profile(set_as_default=False)

        self.assertEqual(result, "staging-admin")
        pm.credentials_manager.set_current_profile.assert_called_once_with("staging-admin")
        pm.credentials_manager.set_default_profile.assert_not_called()
        mock_identity.assert_called_once_with(profile_name="staging-admin")

    @patch("boto3.Session")
    @patch("aws_auth.profile_manager.display_caller_identity")
    def test_switch_profile_sets_default_when_opted_in(self, mock_identity, mock_boto):
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_session.client.return_value = mock_sts
        mock_boto.return_value = mock_session

        pm = ProfileManager()
        pm.credentials_manager = MagicMock()
        pm.credentials_manager.get_existing_profiles.return_value = {"staging-admin"}
        pm.credentials_manager.get_active_profile.return_value = None
        pm.credentials_manager.get_profile_info.return_value = {
            "aws_access_key_id": "AKIA...",
            "aws_session_token": "token...",
            "region": "us-east-1"
        }
        pm.credentials_manager.set_default_profile.return_value = True
        pm.ui.select_profile_to_use = MagicMock(return_value="staging-admin")

        result = pm.switch_profile(set_as_default=True)

        self.assertEqual(result, "staging-admin")
        pm.credentials_manager.set_current_profile.assert_called_once_with("staging-admin")
        pm.credentials_manager.set_default_profile.assert_called_once_with("staging-admin")


class TestCLIArgs(unittest.TestCase):
    """Test CLI argument parsing for current-profile and write-default."""

    def setUp(self):
        self.parser = create_parser()

    def test_current_profile_flag(self):
        args = self.parser.parse_args(["--current-profile"])
        self.assertTrue(args.current_profile)

    def test_write_default_flag(self):
        args = self.parser.parse_args(["--write-default"])
        self.assertTrue(args.write_default)

    def test_switch_profile_flag(self):
        args = self.parser.parse_args(["-s"])
        self.assertTrue(args.switch_profile)
        args2 = self.parser.parse_args(["--switch-profile"])
        self.assertTrue(args2.switch_profile)


class TestEnvironmentSanitization(unittest.TestCase):
    """Test suite for environment sanitization when orphaned AWS_PROFILE is present."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cm = CredentialsManager()
        self.cm.credentials_path = os.path.join(self.temp_dir.name, "credentials")
        self.cm.aws_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_profile_exists(self):
        # Empty file / non-existent
        self.assertFalse(self.cm.profile_exists("nonexistent"))
        self.assertFalse(self.cm.profile_exists(""))

        # Add profile to credentials
        with open(self.cm.credentials_path, "w") as f:
            f.write("[staging-admin]\naws_access_key_id = test\n")
        self.assertTrue(self.cm.profile_exists("staging-admin"))
        self.assertFalse(self.cm.profile_exists("prod-admin"))

    def test_sanitize_environment_purges_orphaned_profile(self):
        # Setup: credentials path has no profiles
        with patch.dict(os.environ, {"AWS_PROFILE": "ghost-profile", "AWS_DEFAULT_PROFILE": "ghost-default"}):
            self.cm.sanitize_environment()
            self.assertNotIn("AWS_PROFILE", os.environ)
            self.assertNotIn("AWS_DEFAULT_PROFILE", os.environ)

    def test_sanitize_environment_preserves_valid_profile(self):
        with open(self.cm.credentials_path, "w") as f:
            f.write("[valid-profile]\naws_access_key_id = test\n")

        with patch.dict(os.environ, {"AWS_PROFILE": "valid-profile"}):
            self.cm.sanitize_environment()
            self.assertEqual(os.environ.get("AWS_PROFILE"), "valid-profile")

    def test_create_unauthenticated_client_with_orphaned_profile(self):
        from aws_auth.sso_client import create_unauthenticated_client
        # Even with nonexistent AWS_PROFILE, client should create successfully without ProfileNotFound
        with patch.dict(os.environ, {"AWS_PROFILE": "nonexistent-profile-xyz"}):
            client = create_unauthenticated_client("sso-oidc", "us-east-1")
            self.assertIsNotNone(client)


if __name__ == "__main__":
    unittest.main()
