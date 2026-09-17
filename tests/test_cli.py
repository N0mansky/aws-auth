"""Tests for aws_auth.cli."""

import unittest
from unittest.mock import patch
from aws_auth.user_interface import UserInterface
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

    def test_delete_arguments(self):
        args = self.parser.parse_args(["--delete"])
        self.assertEqual(args.delete, "")
        args2 = self.parser.parse_args(["--delete", "staging"])
        self.assertEqual(args2.delete, "staging")

    def test_set_default_arguments(self):
        args = self.parser.parse_args(["--set-default"])
        self.assertEqual(args.set_default, "")
        args2 = self.parser.parse_args(["--set-default", "staging"])
        self.assertEqual(args2.set_default, "staging")

    def test_json_and_non_interactive_arguments(self):
        args = self.parser.parse_args(["--list-profiles", "--json", "--non-interactive"])
        self.assertTrue(args.list_profiles)
        self.assertTrue(args.json)
        self.assertTrue(args.non_interactive)

    def test_current_profile_and_write_default_arguments(self):
        args = self.parser.parse_args(["--current-profile", "--write-default"])
        self.assertTrue(args.current_profile)
        self.assertTrue(args.write_default)

    def test_version_string(self):
        self.assertEqual(__version__, "1.2.2")


class TestUserInterfacePrompt(unittest.TestCase):
    @patch('builtins.input', return_value='1')
    def test_prompt_choice_valid(self, mock_input):
        choice = UserInterface.prompt_choice("Select", 3)
        self.assertEqual(choice, 0)

    @patch('builtins.input', return_value='')
    def test_prompt_choice_default(self, mock_input):
        choice = UserInterface.prompt_choice("Select", 3, default=2)
        self.assertEqual(choice, 1)

    @patch('builtins.input', return_value='q')
    def test_prompt_choice_quit_q(self, mock_input):
        choice = UserInterface.prompt_choice("Select", 3)
        self.assertIsNone(choice)

    @patch('builtins.input', return_value='0')
    def test_prompt_choice_quit_zero(self, mock_input):
        choice = UserInterface.prompt_choice("Select", 3)
        self.assertIsNone(choice)

    @patch('builtins.input', return_value='exit')
    def test_prompt_choice_quit_exit(self, mock_input):
        choice = UserInterface.prompt_choice("Select", 3)
        self.assertIsNone(choice)

    @patch('builtins.input', return_value='q')
    def test_select_profile_for_deletion_quit(self, mock_input):
        selected = UserInterface.select_profile_for_deletion(['default', 'dev', 'prod'])
        self.assertIsNone(selected)

    @patch('builtins.input', return_value='')
    def test_select_profile_to_use_defaults_to_first(self, mock_input):
        selected = UserInterface.select_profile_to_use(['staging-admin', 'dev-admin'])
        self.assertEqual(selected, 'dev-admin')  # sorted alphabetically

    @patch('builtins.input', return_value='')
    def test_select_eks_cluster_defaults_to_first(self, mock_input):
        clusters = [{'name': 'cluster-a', 'status': 'ACTIVE'}, {'name': 'cluster-b', 'status': 'ACTIVE'}]
        selected = UserInterface.select_eks_cluster(clusters)
        self.assertEqual(selected, clusters[0])

    @patch('builtins.input', return_value='')
    def test_select_ec2_instance_defaults_to_first(self, mock_input):
        instances = [{'instance_id': 'i-111', 'name': 'app-1', 'state': 'running'}, {'instance_id': 'i-222', 'name': 'app-2', 'state': 'running'}]
        selected = UserInterface.select_ec2_instance(instances)
        self.assertEqual(selected, instances[0])

    @patch('builtins.input', return_value='')
    def test_show_profile_menu_defaults_to_1(self, mock_input):
        choice = UserInterface.show_profile_menu()
        self.assertEqual(choice, '1')

if __name__ == "__main__":
    unittest.main()
