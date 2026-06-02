"""Unit tests for gimme_aws_creds.config.Config"""
import os
import unittest
from unittest.mock import patch

from gimme_aws_creds import ui, errors
from gimme_aws_creds.config import Config
from tests.helpers import make_args
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
        return_value=make_args(username="ann"),
    )
    def test_get_args_username(self, mock_arg):
        """Test to make sure username gets returned"""
        self.config.get_args()
        self.assertEqual(self.config.username, "ann")

    def test_get_args_aws_cred_profile_set(self):
        """Test that --aws-cred-profile is stored on Config when provided"""
        test_ui = MockUserInterface(argv=[
            'gimme-aws-creds', '--aws-cred-profile', 'my-custom-profile',
        ])
        config = Config(gac_ui=test_ui, create_config=False)
        config.get_args()
        self.assertEqual(config.cred_profile, "my-custom-profile")

    def test_get_args_aws_cred_profile_not_set(self):
        """Test that cred_profile is None on Config when --aws-cred-profile is not provided"""
        test_ui = MockUserInterface(argv=['gimme-aws-creds'])
        config = Config(gac_ui=test_ui, create_config=False)
        config.get_args()
        self.assertIsNone(config.cred_profile)

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=make_args(enable_alicloud=True),
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
        return_value=make_args(username="cli_user"),
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
        return_value=make_args(profile="custom_profile"),
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
        return_value=make_args(profile="myprofile", output_format="json"),
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


class TestConfigDebugTracking(unittest.TestCase):
    """Tests for the --debug provenance tracking attributes on Config:
    _cli_args_provided, _env_used_in_init, _inheritance_chain,
    _profile_value_sources, and the log_resolved_configuration() method.
    """

    def test_init_tracks_no_env_when_none_set(self):
        """When no relevant env vars are set, _env_used_in_init is empty."""
        test_ui = MockUserInterface(environ={}, argv=[])
        config = Config(gac_ui=test_ui, create_config=False)
        self.assertEqual(config._env_used_in_init, {})

    def test_init_tracks_okta_username_env_var(self):
        """OKTA_USERNAME env var should be recorded in _env_used_in_init."""
        test_ui = MockUserInterface(environ={'OKTA_USERNAME': 'env_user'}, argv=[])
        config = Config(gac_ui=test_ui, create_config=False)
        self.assertIn('OKTA_USERNAME', config._env_used_in_init)
        self.assertEqual(
            config._env_used_in_init['OKTA_USERNAME']['sets'],
            'config.username',
        )
        self.assertEqual(
            config._env_used_in_init['OKTA_USERNAME']['value'],
            'env_user',
        )

    def test_init_tracks_okta_api_key_env_var(self):
        """OKTA_API_KEY env var should be recorded in _env_used_in_init."""
        test_ui = MockUserInterface(environ={'OKTA_API_KEY': 'secret-key'}, argv=[])
        config = Config(gac_ui=test_ui, create_config=False)
        self.assertIn('OKTA_API_KEY', config._env_used_in_init)
        self.assertEqual(
            config._env_used_in_init['OKTA_API_KEY']['sets'],
            'config.api_key',
        )

    def test_init_tracks_okta_config_env_var(self):
        """OKTA_CONFIG env var should be recorded with target 'config file path'."""
        test_ui = MockUserInterface(
            environ={'OKTA_CONFIG': '/tmp/custom.ini'},
            argv=[],
        )
        config = Config(gac_ui=test_ui, create_config=False)
        self.assertIn('OKTA_CONFIG', config._env_used_in_init)
        self.assertEqual(
            config._env_used_in_init['OKTA_CONFIG']['sets'],
            'config file path',
        )
        self.assertEqual(
            config._env_used_in_init['OKTA_CONFIG']['value'],
            '/tmp/custom.ini',
        )

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=make_args(),
    )
    def test_get_args_no_cli_flags_provided(self, mock_arg):
        """When all argparse values match defaults, _cli_args_provided is empty."""
        test_ui = MockUserInterface(argv=[])
        config = Config(gac_ui=test_ui, create_config=False)
        config.get_args()
        self.assertEqual(config._cli_args_provided, {})

    @patch(
        "argparse.ArgumentParser.parse_args",
        return_value=make_args(
            username='alice',
            debug=True,
            profile='myprof',
            output_format='json',
        ),
    )
    def test_get_args_records_only_provided_flags(self, mock_arg):
        """Only flags that differ from argparse defaults are recorded."""
        test_ui = MockUserInterface(argv=[])
        config = Config(gac_ui=test_ui, create_config=False)
        config.get_args()
        # Provided flags should be in _cli_args_provided
        self.assertEqual(config._cli_args_provided.get('username'), 'alice')
        self.assertEqual(config._cli_args_provided.get('debug'), True)
        self.assertEqual(config._cli_args_provided.get('profile'), 'myprof')
        self.assertEqual(config._cli_args_provided.get('output_format'), 'json')
        # Non-provided flags (matching their defaults) should NOT be recorded
        self.assertNotIn('insecure', config._cli_args_provided)
        self.assertNotIn('remember_device', config._cli_args_provided)
        self.assertNotIn('force_classic', config._cli_args_provided)
        self.assertNotIn('action_configure', config._cli_args_provided)

    def test_handle_config_records_inheritance_chain_single(self):
        """A simple (non-inheriting) profile produces a 1-element chain."""
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write("[myprofile]\nclient_id = foo\n")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        config.get_config_dict()
        self.assertEqual(config._inheritance_chain, ['myprofile'])

    def test_handle_config_records_inheritance_chain_with_parent(self):
        """Inheritance chain is recorded child-first."""
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write("""
[mybase]
client_id = base_id
[myprofile]
inherits = mybase
aws_appname = MyApp
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        config.get_config_dict()
        self.assertEqual(config._inheritance_chain, ['myprofile', 'mybase'])

    def test_handle_config_records_inheritance_chain_nested(self):
        """Multi-level inheritance is recorded child -> parent -> grandparent."""
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write("""
[grandparent]
client_id = gp_id
[parent]
inherits = grandparent
aws_appname = ParentApp
[myprofile]
inherits = parent
aws_rolename = MyRole
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        config.get_config_dict()
        self.assertEqual(
            config._inheritance_chain,
            ['myprofile', 'parent', 'grandparent'],
        )

    def test_profile_value_sources_attributes_keys_to_owning_profile(self):
        """Each conf_dict key should be tagged with the profile that defines it.

        Child overrides parent: keys in both are tagged with the child profile.
        """
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write("""
[mybase]
client_id = base_id
aws_appname = BaseApp
gimme_creds_server = appurl
[myprofile]
inherits = mybase
client_id = child_id
aws_rolename = MyRole
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        config.get_config_dict()
        sources = config._profile_value_sources
        # Child overrides parent for client_id
        self.assertEqual(sources.get('client_id'), 'myprofile')
        # Net-new keys in child get tagged to child
        self.assertEqual(sources.get('aws_rolename'), 'myprofile')
        # Parent-only keys get tagged to parent
        self.assertEqual(sources.get('aws_appname'), 'mybase')
        self.assertEqual(sources.get('gimme_creds_server'), 'mybase')
        # 'inherits' key is consumed and not tracked
        self.assertNotIn('inherits', sources)

    def test_log_resolved_configuration_emits_debug_output(self):
        """log_resolved_configuration emits a structured message at DEBUG level."""
        import logging

        test_ui = MockUserInterface(
            environ={'OKTA_USERNAME': 'env_user'},
            argv=['--profile', 'myprofile'],
        )
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write("""
[myprofile]
client_id = foo
okta_org_url = https://example.okta.com
""")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        conf_dict = config.get_config_dict()

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            config.log_resolved_configuration(
                conf_dict,
                env_overrides_applied={'okta_username': 'OKTA_USERNAME'},
                cli_overrides_applied={},
            )

        full_output = '\n'.join(captured.output)
        # Section headers should be present
        self.assertIn('RESOLVED CONFIGURATION', full_output)
        self.assertIn('Configuration file:', full_output)
        self.assertIn('Active profile:', full_output)
        self.assertIn('myprofile', full_output)
        # The override should be visible with its source
        self.assertIn('OKTA_USERNAME', full_output)
        self.assertIn('env: OKTA_USERNAME', full_output)
        # Profile-sourced values are tagged with the profile name
        self.assertIn('profile: myprofile', full_output)
        self.assertIn('client_id', full_output)
        self.assertIn('okta_org_url', full_output)

    def test_log_resolved_configuration_handles_none_overrides(self):
        """log_resolved_configuration accepts None for the overrides args."""
        import logging

        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write("[myprofile]\nclient_id = foo\n")
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = "myprofile"
        conf_dict = config.get_config_dict()

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            config.log_resolved_configuration(conf_dict)

        # Should produce output without raising
        self.assertTrue(any('RESOLVED CONFIGURATION' in m for m in captured.output))
