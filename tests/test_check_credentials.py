"""Unit tests for the credential and secret scanner (scripts/check_credentials.py)."""

import unittest
from scripts.check_credentials import (
    scan_content,
    check_file_path,
    is_suppressed,
    is_known_safe,
    mask_secret,
)


class TestCredentialChecker(unittest.TestCase):
    """Test suite for credential check logic."""

    def test_aws_access_key_detection(self):
        # Construct fake keys dynamically to avoid triggering scanners on test files
        fake_akia = "AKIA" + "1234567890ABCDEF"
        content = f"aws_key = '{fake_akia}'"
        findings = scan_content(content, "some_file.py")
        self.assertEqual(len(findings), 1)
        self.assertIn("AWS Access Key ID", findings[0]["rule"])

    def test_aws_session_key_detection(self):
        fake_asia = "ASIA" + "1234567890ABCDEF"
        content = f"aws_temp_key = '{fake_asia}'"
        findings = scan_content(content, "some_file.py")
        self.assertEqual(len(findings), 1)
        self.assertIn("AWS Access Key ID", findings[0]["rule"])

    def test_private_key_detection(self):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."  # pragma: allowlist secret
        findings = scan_content(content, "key_file.txt")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "Private Key Header")

    def test_github_pat_detection(self):
        fake_pat = "ghp_" + "a" * 36
        content = f"GITHUB_TOKEN = '{fake_pat}'"
        findings = scan_content(content, "config.py")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "GitHub Personal Access Token")

    def test_suppression_directives(self):
        fake_akia = "AKIA" + "9999999999ABCDEF"
        line1 = f"key = '{fake_akia}' # pragma: allowlist secret"
        line2 = f"key = '{fake_akia}' # nosec"
        self.assertTrue(is_suppressed(line1))
        self.assertTrue(is_suppressed(line2))

        findings = scan_content(line1, "module.py")
        self.assertEqual(len(findings), 0)

    def test_blocked_file_patterns(self):
        self.assertIsNotNone(check_file_path("server.pem"))
        self.assertIsNotNone(check_file_path("private.key"))
        self.assertIsNotNone(check_file_path(".env"))
        self.assertIsNotNone(check_file_path(".env.production"))
        self.assertIsNotNone(check_file_path("sso_access_token.json"))
        self.assertIsNone(check_file_path("README.md"))
        self.assertIsNone(check_file_path("aws_auth/cli.py"))

    def test_mask_secret(self):
        test_key = "AKIA" + "1234567890ABCDEF"  # pragma: allowlist secret
        self.assertEqual(mask_secret(test_key), "AKIA...CDEF")
        self.assertEqual(mask_secret("short"), "****")


if __name__ == "__main__":
    unittest.main()
