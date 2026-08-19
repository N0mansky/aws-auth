"""Tests for aws_auth.config."""

import unittest
from aws_auth.config import Config


class TestConfig(unittest.TestCase):
    def test_config_defaults(self):
        config = Config()
        config.SSO_START_URL = "https://example.awsapps.com/start"
        self.assertEqual(config.SSO_REGION, "us-east-1")
        self.assertTrue(config.SSO_START_URL.startswith("https://"))
        self.assertTrue(config.validate())

    def test_config_validation_failure(self):
        config = Config()
        config.SSO_START_URL = ""
        self.assertFalse(config.validate())
        config.SSO_START_URL = "https://example.awsapps.com/start"
        config.SSO_REGION = ""
        self.assertFalse(config.validate())

    def test_recent_selections_and_aliases(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.CACHE_DIR = tmpdir
            config.CONFIG_FILE = os.path.join(tmpdir, "config.json")
            
            # Initially empty
            self.assertEqual(config.get_recent_selections(), [])
            self.assertEqual(config.get_aliases(), {})
            self.assertEqual(config.get_preferred_accounts(), [])
            
            # Record selections
            config.record_recent_selection("111111111111", "DevAccount", "AdminRole")
            config.record_recent_selection("222222222222", "ProdAccount", "ViewRole")
            
            recents = config.get_recent_selections()
            self.assertEqual(len(recents), 2)
            self.assertEqual(recents[0]["accountId"], "222222222222")
            self.assertEqual(recents[1]["accountId"], "111111111111")
            
            # Re-record DevAccount -> should move to front
            config.record_recent_selection("111111111111", "DevAccount", "AdminRole")
            recents = config.get_recent_selections()
            self.assertEqual(len(recents), 2)
            self.assertEqual(recents[0]["accountId"], "111111111111")


if __name__ == "__main__":
    unittest.main()
