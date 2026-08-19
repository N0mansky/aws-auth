"""Tests for aws_auth.cli."""

import unittest
from aws_auth.cli import create_parser
from aws_auth import __version__


class TestCLIParser(unittest.TestCase):
    def setUp(self):
        self.parser = create_parser()

    def test_default_arguments(self):
        args = self.parser.parse_args([])
        self.assertFalse(args.manage)
        self.assertFalse(args.list_profiles)
        self.assertIsNone(args.set_default)
        self.assertIsNone(args.delete)
        self.assertIsNone(args.list_ec2)
        self.assertIsNone(args.list_eks)
        self.assertEqual(args.region, "us-east-1")
        self.assertFalse(args.no_auth)

    def test_list_ec2_arguments(self):
        args = self.parser.parse_args(["--list-ec2", "--region", "us-west-2"])
        self.assertEqual(args.list_ec2, "default")
        self.assertEqual(args.region, "us-west-2")

    def test_mcp_arguments(self):
        args = self.parser.parse_args(["--mcp"])
        self.assertTrue(args.mcp)

    def test_export_env_arguments(self):
        args = self.parser.parse_args(["--export-env"])
        self.assertEqual(args.export_env, "default")
        args2 = self.parser.parse_args(["--export-env", "staging"])
        self.assertEqual(args2.export_env, "staging")

    def test_identity_arguments(self):
        args = self.parser.parse_args(["--identity"])
        self.assertTrue(args.identity)

    def test_credential_process_arguments(self):
        args = self.parser.parse_args(["--credential-process"])
        self.assertEqual(args.credential_process, "default")
        args2 = self.parser.parse_args(["--credential-process", "prod"])
        self.assertEqual(args2.credential_process, "prod")

    def test_refresh_cache_argument(self):
        args = self.parser.parse_args(["--refresh-cache"])
        self.assertTrue(args.refresh_cache)

    def test_configure_argument(self):
        args = self.parser.parse_args(["--configure"])
        self.assertTrue(args.configure)

    def test_json_and_non_interactive_arguments(self):
        args = self.parser.parse_args(["--list-profiles", "--json", "--non-interactive"])
        self.assertTrue(args.list_profiles)
        self.assertTrue(args.json)
        self.assertTrue(args.non_interactive)


if __name__ == "__main__":
    unittest.main()
