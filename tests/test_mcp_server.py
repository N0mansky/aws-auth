"""Tests for aws_auth.mcp_server."""

import unittest
from unittest.mock import patch, MagicMock
from aws_auth.mcp_server import (
    aws_list_profiles,
    aws_switch_profile,
    aws_get_caller_identity,
    aws_get_session_env,
    aws_ensure_credentials
)


class TestMCPServerTools(unittest.TestCase):

    @patch('aws_auth.mcp_server.CredentialsManager')
    def test_aws_list_profiles(self, mock_cm_cls):
        mock_cm = MagicMock()
        mock_cm_cls.return_value = mock_cm
        mock_cm.get_existing_profiles.return_value = {'default', 'dev'}
        mock_cm.get_default_profile_name.return_value = 'dev'
        mock_cm.get_profile_info.side_effect = lambda p: {'region': 'us-west-2', 'aws_access_key_id': 'AKIA...'}
        
        result = aws_list_profiles()
        self.assertTrue(result['success'])
        self.assertEqual(result['default_profile'], 'dev')
        self.assertIn('dev', result['profiles'])
        self.assertTrue(result['profiles']['dev']['has_credentials'])

    @patch('aws_auth.mcp_server.get_caller_identity')
    @patch('aws_auth.mcp_server.CredentialsManager')
    def test_aws_switch_profile(self, mock_cm_cls, mock_identity):
        mock_cm = MagicMock()
        mock_cm_cls.return_value = mock_cm
        mock_cm.get_existing_profiles.return_value = {'default', 'staging'}
        mock_cm.set_default_profile.return_value = True
        mock_identity.return_value = {'Account': '123456789012', 'UserId': 'test-user', 'Arn': 'arn:aws:...'}

        result = aws_switch_profile('staging')
        self.assertTrue(result['success'])
        self.assertEqual(result['active_profile'], 'staging')
        self.assertEqual(result['identity']['Account'], '123456789012')

    @patch('aws_auth.mcp_server.get_caller_identity')
    def test_aws_get_caller_identity(self, mock_identity):
        mock_identity.return_value = {'Account': '123456789012', 'UserId': 'test-user', 'Arn': 'arn:aws:...'}
        result = aws_get_caller_identity('default')
        self.assertTrue(result['success'])
        self.assertEqual(result['identity']['Account'], '123456789012')

    @patch('aws_auth.mcp_server.CredentialsManager')
    def test_aws_get_session_env(self, mock_cm_cls):
        mock_cm = MagicMock()
        mock_cm_cls.return_value = mock_cm
        mock_cm.get_unmasked_profile_credentials.return_value = {
            'aws_access_key_id': 'AKIAEXAMPLEKEY',
            'aws_secret_access_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'aws_session_token': 'AQoDYXdzEJr1...',
            'region': 'us-west-2'
        }

        result = aws_get_session_env('staging')
        self.assertTrue(result['success'])
        self.assertEqual(result['env']['AWS_ACCESS_KEY_ID'], 'AKIAEXAMPLEKEY')
        self.assertEqual(result['env']['AWS_DEFAULT_REGION'], 'us-west-2')
        self.assertEqual(result['env']['AWS_PROFILE'], 'staging')


if __name__ == "__main__":
    unittest.main()
