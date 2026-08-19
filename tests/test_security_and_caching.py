"""Tests for security permissions, atomic writes, and metadata caching."""

import os
import tempfile
import stat
import json
import time
import unittest
from unittest.mock import patch, MagicMock

from aws_auth.config import Config
from aws_auth.credentials_manager import CredentialsManager
from aws_auth.token_manager import TokenManager


class TestSecurityAndCaching(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.credentials_path = os.path.join(self.temp_dir, "credentials")
        self.cache_dir = os.path.join(self.temp_dir, ".aws-auth")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.config = Config()
        self.config.SSO_START_URL = "https://test.awsapps.com/start"
        self.config.SSO_REGION = "us-east-1"
        self.config.CACHE_DIR = self.cache_dir
        self.config.AUTHLY_DIR = self.cache_dir
        self.config.CLIENT_CACHE_FILE = os.path.join(self.cache_dir, "client_cache.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_credentials_atomic_write_and_permissions(self):
        cm = CredentialsManager()
        cm.credentials_path = self.credentials_path
        cm.aws_dir = os.path.dirname(self.credentials_path)

        creds = {
            "accessKeyId": "ASIAEXAMPLE123",
            "secretAccessKey": "SECRET123",
            "sessionToken": "TOKEN123"
        }
        cm.write_credentials(["test-profile"], creds, "us-west-2")

        self.assertTrue(os.path.exists(self.credentials_path))
        
        # Check permissions on POSIX systems
        if os.name != 'nt' and hasattr(os, 'stat'):
            file_stat = os.stat(self.credentials_path)
            mode = stat.S_IMODE(file_stat.st_mode)
            self.assertEqual(mode & 0o777, 0o600)

        unmasked = cm.get_unmasked_profile_credentials("test-profile")
        self.assertIsNotNone(unmasked)
        self.assertEqual(unmasked["aws_access_key_id"], "ASIAEXAMPLE123")

    def test_token_manager_permissions_and_caching(self):
        tm = TokenManager(self.config)
        tm.cache_sso_access_token("test_token_xyz", 3600, "test_refresh_abc")

        token_file = os.path.join(self.cache_dir, "sso_access_token.json")
        self.assertTrue(os.path.exists(token_file))

        if os.name != 'nt' and hasattr(os, 'stat'):
            file_stat = os.stat(token_file)
            mode = stat.S_IMODE(file_stat.st_mode)
            self.assertEqual(mode & 0o777, 0o600)

    def test_accounts_and_roles_caching(self):
        tm = TokenManager(self.config)
        accounts = [{"accountId": "111222333444", "accountName": "Dev"}]
        roles = {"111222333444": [{"roleName": "DevAdmin"}]}

        tm.cache_accounts_and_roles(accounts, roles)
        cached = tm.load_cached_accounts_and_roles(max_age_hours=24)

        self.assertIsNotNone(cached)
        cached_accounts, cached_roles = cached
        self.assertEqual(cached_accounts[0]["accountId"], "111222333444")
        self.assertEqual(cached_roles["111222333444"][0]["roleName"], "DevAdmin")

    def test_token_expiration_safety_margin(self):
        tm = TokenManager(self.config)
        # Token expiring in 200 seconds (within the 300s margin) should be reported as expired
        tm.cache_sso_access_token("expiring_soon_token", 200, "refresh_xyz")
        
        info = tm.get_token_info(use_cache=False)
        self.assertIsNotNone(info)
        self.assertTrue(info["isExpired"], "Tokens within the 300-second margin must be treated as expired for proactive refresh")


if __name__ == "__main__":
    unittest.main()
