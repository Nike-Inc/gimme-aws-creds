"""Unit tests for gimme_aws_creds.config.Config"""
import argparse
import os
import unittest
from unittest.mock import patch

from gimme_aws_creds import ui, errors
from gimme_aws_creds.config import Config
from tests.user_interface_mock import MockUserInterface


class TestConfig(unittest.TestCase):
    """Class to test Config Class.
       Mock is used to mock external calls"""

    def setUp(self):
        """Set up for the unit tests"""
        self.config = Config(gac_ui=ui.cli, create_config=False)

    def tearDown(self):
        """Run Clean Up"""
        self.config.clean_up()

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            username="ann",
            profile=None,
            insecure=False,
            resolve=None,
            mfa_code=None,
            remember_device=False,
            output_format=None,
            roles=None,
            action_register_device=False,
            action_configure=False,
            action_list_profiles=False,
            action_list_roles=False,
            action_store_json_creds=False,
            action_setup_fido_authenticator=False,
            open_browser=False,
            force_classic=False,
            disable_keychain=False,
            debug=False,
            enable_alicloud=False,
        ),
    )
    def test_get_args_username(self, mock_arg):
        """Test to make sure username gets returned"""
        self.config.get_args()
        self.assertEqual(self.config.username, "ann")

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            username=None,
            profile=None,
            insecure=False,
            resolve=None,
            mfa_code=None,
            remember_device=False,
            output_format=None,
            roles=None,
            action_register_device=False,
            action_configure=False,
            action_list_profiles=False,
            action_list_roles=False,
            action_store_json_creds=False,
            action_setup_fido_authenticator=False,
            open_browser=False,
            force_classic=False,
            disable_keychain=False,
            debug=False,
            enable_alicloud=True,
        ),
    )
    def test_get_args_enable_alicloud(self, mock_arg):
        """--enable-alicloud sets config flag"""
        self.config.get_args()
        self.assertTrue(self.config.enable_alicloud)

    def test_read_config(self):
        """Test to make sure getting config works"""
        test_ui = MockUserInterface(argv=[
            "--profile",
            "myprofile",
        ])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
client_id = foo
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config, {"client_id": "foo", 'force_classic': True})

    def test_read_config_enable_alicloud(self):
        """Profile may set enable_alicloud for Alibaba Cloud device scope"""
        test_ui = MockUserInterface(argv=[
            "--profile",
            "myprofile",
        ])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
client_id = foo
enable_alicloud = True
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        self.assertIs(profile_config.get('enable_alicloud'), True)

    def test_read_config_inherited(self):
        """Test to make sure getting config works when inherited"""
        test_ui = MockUserInterface(argv=[
            "--profile",
            "myprofile",
        ])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write(
                """
                [mybase]
                client_id = bar
                aws_appname = baz
                force_classic = True
                [myprofile]
                inherits = mybase
                client_id = foo
                aws_rolename = myrole
                """
            )

        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config, {
            "client_id": "foo",
            "aws_appname": "baz",
            "aws_rolename": "myrole",
            'force_classic': True,
        })

    def test_read_nested_config_inherited(self):
        """Test to make sure getting config works when inherited"""
        test_ui = MockUserInterface(argv = [
            "--profile",
            "myprofile",
        ])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[mybase-level1]
client_id = bar
[mybase-level2]
inherits = mybase-level1
aws_appname = baz
force_classic = 
[myprofile]
inherits = mybase-level2
client_id = foo
aws_rolename = myrole
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config, {
            "client_id": "foo",
            "aws_appname": "baz",
            "aws_rolename": "myrole",
            "force_classic": True
        })

    def test_read_nested_config_inherited_no_force_classic(self):
        """Test to make sure getting config works when inherited"""
        test_ui = MockUserInterface(argv = [
            "--profile",
            "myprofile",
        ])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[mybase-level1]
client_id = bar
[mybase-level2]
inherits = mybase-level1
aws_appname = baz
force_classic = False
[myprofile]
inherits = mybase-level2
client_id = foo
aws_rolename = myrole
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config, {
            "client_id": "foo",
            "aws_appname": "baz",
            "aws_rolename": "myrole",
            "force_classic": False
        })

    def test_fail_if_profile_not_found(self):
        """Test to make sure missing Default fails properly"""
        test_ui = MockUserInterface(argv=[])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
        [myprofile]
        client_id = foo
        """)
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "DEFAULT"
        with self.assertRaises(errors.GimmeAWSCredsError) as context:
            config.get_config_dict()
        self.assertTrue('DEFAULT profile is missing! This is profile is required when not using --profile' == context.exception.message)

    def test_env_var_okta_username_overrides_config_file(self):
        """AC2: Test that OKTA_USERNAME env var overrides config file username"""
        test_ui = MockUserInterface(
            environ={'OKTA_USERNAME': 'env_user'},
            argv=['--profile', 'myprofile']
        )
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
okta_username = file_user
client_id = foo
""")
        config = Config(gac_ui=test_ui, create_config=False)
        # Env var should be set in __init__
        self.assertEqual(config.username, 'env_user')

    def test_env_var_okta_api_key_overrides_config_file(self):
        """AC2: Test that OKTA_API_KEY env var overrides config file api_key"""
        test_ui = MockUserInterface(
            environ={'OKTA_API_KEY': 'env_api_key_123'},
            argv=['--profile', 'myprofile']
        )
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
client_id = foo
""")
        config = Config(gac_ui=test_ui, create_config=False)
        # Env var should be set in __init__
        self.assertEqual(config.api_key, 'env_api_key_123')

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            username="cli_user",
            profile=None,
            insecure=False,
            resolve=None,
            mfa_code=None,
            remember_device=False,
            output_format=None,
            roles=None,
            action_register_device=False,
            action_configure=False,
            action_list_profiles=False,
            action_list_roles=False,
            action_store_json_creds=False,
            action_setup_fido_authenticator=False,
            open_browser=False,
            force_classic=False,
            disable_keychain=False,
            debug=False,
            enable_alicloud=False,
        ),
    )
    def test_cli_arg_username_overrides_env_var(self, mock_arg):
        """AC3: Test that CLI --username overrides OKTA_USERNAME env var"""
        test_ui = MockUserInterface(
            environ={'OKTA_USERNAME': 'env_user'},
            argv=['--username', 'cli_user']
        )
        config = Config(gac_ui=test_ui, create_config=False)
        # Env var set in __init__
        self.assertEqual(config.username, 'env_user')
        # CLI arg should override in get_args()
        config.get_args()
        self.assertEqual(config.username, 'cli_user')

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            username=None,
            profile="custom_profile",
            insecure=False,
            resolve=None,
            mfa_code=None,
            remember_device=False,
            output_format=None,
            roles=None,
            action_register_device=False,
            action_configure=False,
            action_list_profiles=False,
            action_list_roles=False,
            action_store_json_creds=False,
            action_setup_fido_authenticator=False,
            open_browser=False,
            force_classic=False,
            disable_keychain=False,
            debug=False,
            enable_alicloud=False,
        ),
    )
    def test_cli_arg_profile_overrides_default(self, mock_arg):
        """AC3: Test that CLI --profile overrides DEFAULT profile"""
        test_ui = MockUserInterface(
            argv=['--profile', 'custom_profile']
        )
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[DEFAULT]
client_id = default_client
[custom_profile]
client_id = custom_client
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.get_args()
        self.assertEqual(config.conf_profile, 'custom_profile')
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config['client_id'], 'custom_client')

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(
            username=None,
            profile="myprofile",
            insecure=False,
            resolve=None,
            mfa_code=None,
            remember_device=False,
            output_format="json",
            roles=None,
            action_register_device=False,
            action_configure=False,
            action_list_profiles=False,
            action_list_roles=False,
            action_store_json_creds=False,
            action_setup_fido_authenticator=False,
            open_browser=False,
            force_classic=False,
            disable_keychain=False,
            debug=False,
            enable_alicloud=False,
        ),
    )
    def test_cli_arg_output_format_overrides_config_file(self, mock_arg):
        """AC3: Test that CLI --output-format overrides config file"""
        test_ui = MockUserInterface(
            argv=['--output-format', 'json', '--profile', 'myprofile']
        )
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
output_format = export
client_id = foo
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.get_args()
        # CLI arg should override config file
        self.assertEqual(config.output_format, 'json')
        self.assertEqual(config.action_output_format, 'json')

    def test_okta_config_env_var_overrides_default_path(self):
        """Test that OKTA_CONFIG env var overrides default config file path"""
        custom_config_path = '/tmp/custom_okta_config.ini'
        test_ui = MockUserInterface(
            environ={'OKTA_CONFIG': custom_config_path},
            argv=[]
        )
        # Create config file at custom path
        with open(custom_config_path, "w") as config_file:
            config_file.write("""
[DEFAULT]
client_id = custom_path_client
""")
        config = Config(gac_ui=test_ui, create_config=False)
        self.assertEqual(config.OKTA_CONFIG, custom_config_path)
        # Verify it reads from custom path
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config['client_id'], 'custom_path_client')
        # Cleanup
        os.unlink(custom_config_path)

    def test_profile_inheritance_missing_parent_raises_error(self):
        """Test that inheriting from non-existent profile raises error"""
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
inherits = nonexistent_profile
client_id = foo
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        with self.assertRaises(errors.GimmeAWSCredsError) as context:
            config.get_config_dict()
        self.assertIn('inherits from nonexistent_profile', str(context.exception))
        self.assertIn('could not find nonexistent_profile', str(context.exception))

    def test_profile_inheritance_circular_reference_raises_error(self):
        """Test that circular inheritance raises error"""
        test_ui = MockUserInterface(argv=['--profile', 'profile_a'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[profile_a]
inherits = profile_b
client_id = a
[profile_b]
inherits = profile_a
client_id = b
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "profile_a"
        # Circular reference should cause recursion error or similar
        with self.assertRaises(Exception):
            config.get_config_dict()

    def test_config_file_reading_with_valid_ini_format(self):
        """AC1: Test reading valid config file with various INI formats"""
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
client_id = test_client_123
okta_org_url = https://example.okta.com
aws_rolename = arn:aws:iam::123456789012:role/TestRole
write_aws_creds = True
aws_default_duration = 7200
force_classic = False
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        self.assertEqual(profile_config['client_id'], 'test_client_123')
        self.assertEqual(profile_config['okta_org_url'], 'https://example.okta.com')
        self.assertEqual(profile_config['aws_rolename'], 'arn:aws:iam::123456789012:role/TestRole')
        self.assertEqual(profile_config['write_aws_creds'], True)
        self.assertEqual(profile_config['aws_default_duration'], '7200')
        self.assertEqual(profile_config['force_classic'], False)

    def test_config_file_reading_with_empty_values(self):
        """AC1: Test reading config file with empty values"""
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as config_file:
            config_file.write("""
[myprofile]
client_id = 
okta_org_url = https://example.okta.com
aws_rolename = 
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        profile_config = config.get_config_dict()
        # Empty values should be handled gracefully
        self.assertEqual(profile_config.get('client_id'), '')
        self.assertEqual(profile_config.get('aws_rolename'), '')
