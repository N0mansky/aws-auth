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
    @patch("aws_auth.cli.EC2Manager")
    @patch("aws_auth.cli.UserInterface")
    def test_choice_1_lists_ec2(self, mock_ui_cls, mock_ec2_cls, mock_input):
        mock_ec2 = MagicMock()
        mock_ec2_cls.return_value = mock_ec2
        mock_ec2.list_instances.return_value = []
        offer_resource_exploration("test-profile", "us-east-1")
        mock_ec2.list_instances.assert_called_once_with("us-east-1")

    @patch("builtins.input", return_value="2")
    @patch("aws_auth.cli.EKSManager")
    @patch("aws_auth.cli.UserInterface")
    def test_choice_2_lists_eks(self, mock_ui_cls, mock_eks_cls, mock_input):
        mock_eks = MagicMock()
        mock_eks_cls.return_value = mock_eks
        mock_eks.list_clusters.return_value = []
        offer_resource_exploration("test-profile", "us-east-1")
        mock_eks.list_clusters.assert_called_once_with("us-east-1")


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


if __name__ == "__main__":
    unittest.main()
