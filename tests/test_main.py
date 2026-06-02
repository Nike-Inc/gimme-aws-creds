import shutil
import unittest
from unittest.mock import patch

from gimme_aws_creds import errors
from gimme_aws_creds.common import RoleSet
from gimme_aws_creds.main import GimmeAWSCreds
from tests.user_interface_mock import MockUserInterface


class TestMain(unittest.TestCase):
    APP_INFO = [
        RoleSet(idp='idp', role='test1', friendly_account_name='', friendly_role_name=''),
        RoleSet(idp='idp', role='test2', friendly_account_name='', friendly_role_name='')
    ]

    AWS_INFO = [
        {'name': 'test1'},
        {'name': 'test2'}
    ]

    @patch('builtins.input', return_value='-1')
    def test_choose_roles_app_neg1(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_roles, self.APP_INFO)
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_app, self.AWS_INFO)

    @patch('builtins.input', return_value='0')
    def test_choose_roles_app_0(self, mock):
        creds = GimmeAWSCreds()
        selections = creds._choose_roles(self.APP_INFO)
        self.assertEqual(selections, {self.APP_INFO[0].role})

        selections = creds._choose_roles(self.APP_INFO)
        self.assertEqual(selections, {self.APP_INFO[0].role})

    @patch('builtins.input', return_value='1')
    def test_choose_roles_app_1(self, mock):
        creds = GimmeAWSCreds()
        selections = creds._choose_roles(self.APP_INFO)
        self.assertEqual(selections, {self.APP_INFO[1].role})

        selections = creds._choose_roles(self.APP_INFO)
        self.assertEqual(selections, {self.APP_INFO[1].role})

    @patch('builtins.input', return_value='2')
    def test_choose_roles_app_2(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_roles, self.APP_INFO)
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_app, self.AWS_INFO)

    @patch('builtins.input', return_value='b')
    def test_choose_roles_app_b(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_roles, self.APP_INFO)
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_app, self.AWS_INFO)

    @patch('builtins.input', return_value='all')
    def test_choose_roles_app_select_all(self, mock):
        creds = GimmeAWSCreds()
        selections = creds._choose_roles(self.APP_INFO)
        expected_selections = {self.APP_INFO[0].role, self.APP_INFO[1].role}
        self.assertEqual(selections, expected_selections)
        
    @patch('builtins.input', return_value='a')
    def test_choose_roles_app_select_all_a(self, mock):
        creds = GimmeAWSCreds()
        selections = creds._choose_roles(self.APP_INFO)
        expected_selections = {self.APP_INFO[0].role, self.APP_INFO[1].role}
        self.assertEqual(selections, expected_selections)
        
    def test_get_selected_app_from_config_0(self):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_app('test1', self.AWS_INFO)
        self.assertEqual(selection, self.AWS_INFO[0])

    def test_get_selected_app_from_config_1(self):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_app('test2', self.AWS_INFO)
        self.assertEqual(selection, self.AWS_INFO[1])

    @patch('builtins.input', return_value='0')
    def test_missing_app_from_config(self, mock):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_app('test3', self.AWS_INFO)
        self.assertEqual(selection, self.AWS_INFO[0])

    def test_get_selected_roles_from_config_0(self):
        creds = GimmeAWSCreds()

        selections = creds._get_selected_roles('test1', self.APP_INFO)
        self.assertEqual(selections, {'test1'})

    def test_get_selected_roles_from_config_1(self):
        creds = GimmeAWSCreds()

        selections = creds._get_selected_roles('test2', self.APP_INFO)
        self.assertEqual(selections, {'test2'})

    def test_get_selected_roles_multiple(self):
        creds = GimmeAWSCreds()

        selections = creds._get_selected_roles('test1, test2', self.APP_INFO)
        self.assertEqual(selections, {'test1', 'test2'})

    def test_get_selected_roles_multiple_list(self):
        creds = GimmeAWSCreds()

        selections = creds._get_selected_roles(['test1', 'test2'], self.APP_INFO)
        self.assertEqual(selections, {'test1', 'test2'})

    def test_get_selected_roles_all(self):
        creds = GimmeAWSCreds()

        selections = creds._get_selected_roles('all', self.APP_INFO)
        self.assertEqual(selections, {'test1', 'test2'})

    @patch('builtins.input', return_value='0')
    def test_missing_role_from_config(self, mock):
        creds = GimmeAWSCreds()

        selections = creds._get_selected_roles('test3', self.APP_INFO)
        self.assertEqual(selections, {'test1'})

    def test_get_partition_aws(self):
        creds = GimmeAWSCreds()

        partition, region = creds._get_partition_and_region_from_saml_acs('https://signin.aws.amazon.com/saml')
        self.assertEqual(partition, 'aws')
        self.assertEqual(region, 'us-east-1')

    def test_get_region_partition_aws(self):
        creds = GimmeAWSCreds()

        partition, region = creds._get_partition_and_region_from_saml_acs('https://us-west-2.signin.aws.amazon.com/saml')
        self.assertEqual(partition, 'aws')
        self.assertEqual(region, 'us-west-2')

    def test_get_partition_china(self):
        creds = GimmeAWSCreds()

        partition, region = creds._get_partition_and_region_from_saml_acs('https://signin.amazonaws.cn/saml')
        self.assertEqual(partition, 'aws-cn')
        self.assertEqual(region, 'cn-north-1')

    def test_get_region_partition_china(self):
        creds = GimmeAWSCreds()

        partition, region = creds._get_partition_and_region_from_saml_acs('https://cn-northwest-1.signin.amazonaws.cn/saml')
        self.assertEqual(partition, 'aws-cn')
        self.assertEqual(region, 'cn-northwest-1')

    def test_get_partition_govcloud(self):
        creds = GimmeAWSCreds()

        partition, region = creds._get_partition_and_region_from_saml_acs('https://signin.amazonaws-us-gov.com/saml')
        self.assertEqual(partition, 'aws-us-gov')
        self.assertEqual(region, 'us-gov-east-1')

    def test_get_region_partition_govcloud(self):
        creds = GimmeAWSCreds()

        partition, region = creds._get_partition_and_region_from_saml_acs('https://us-gov-east-2.signin.amazonaws-us-gov.com/saml')
        self.assertEqual(partition, 'aws-us-gov')
        self.assertEqual(region, 'us-gov-east-2')

    def test_get_partition_unkown(self):
        creds = GimmeAWSCreds()

        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._get_partition_and_region_from_saml_acs,
                          'https://signin.amazonaws-foo.com/saml')

    def test_parse_role_arn_base_path(self):
        creds = GimmeAWSCreds()
        arn = "arn:aws:iam::123456789012:role/okta-1234-role"
        self.assertEqual(creds._parse_role_arn(arn),
                         {
                             'account': '123456789012',
                             'path': '/',
                             'role': 'okta-1234-role'
                         })

    def test_parse_role_arn_extended_path(self):
        creds = GimmeAWSCreds()
        arn = "arn:aws:iam::123456789012:role/a/really/extended/path/okta-1234-role"
        self.assertEqual(creds._parse_role_arn(arn),
                         {
                             'account': '123456789012',
                             'path': '/a/really/extended/path/',
                             'role': 'okta-1234-role'
                         })

    def test_get_alias_from_friendly_name_no_alias(self):
        creds = GimmeAWSCreds()
        friendly_name = "Account: 123456789012"
        self.assertEqual(creds._get_alias_from_friendly_name(friendly_name), None)

    def test_get_alias_from_friendly_name_with_alias(self):
        creds = GimmeAWSCreds()
        friendly_name = "Account: my-account-org (123456789012)"
        self.assertEqual(creds._get_alias_from_friendly_name(friendly_name), "my-account-org")


    def test_get_profile_name_accrole_resolve_alias_do_not_include_paths(self):
        "Testing the acc-role, with alias resolution, and not including full role path"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/administrator/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/administrator/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'acc-role'
        resolve_alias = True
        include_path = False
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role), "my-org-master-administrator")

    def test_get_profile_accrole_name_do_not_resolve_alias_do_not_include_paths(self):
        "Testing the acc-role, without alias resolution, and not including full role path"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/administrator/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/administrator/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'acc-role'
        resolve_alias = False
        include_path = False
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         "123456789012-administrator")

    def test_get_profile_accrole_name_do_not_resolve_alias_include_paths(self):
        "Testing the acc-role, without alias resolution, and including full role path"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/some/long/extended/path/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/some/long/extended/path/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'acc-role'
        resolve_alias = False
        include_path = True
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         "123456789012-/some/long/extended/path/administrator")

    def test_get_profile_name_role(self):
        "Testing the role"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/some/long/extended/path/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/some/long/extended/path/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'role'
        resolve_alias = False
        include_path = True
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         'administrator')

    def test_get_profile_name_account_resolve_alias(self):
        "Testing the account with alias resolution"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/administrator/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/administrator/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'acc'
        resolve_alias = True
        include_path = True
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         'my-org-master')

    def test_get_profile_name_account_do_not_resolve_alias(self):
        "Testing the account without alias resolution"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/administrator/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/administrator/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'acc'
        resolve_alias = False
        include_path = True
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         '123456789012')

    def test_get_profile_name_default(self):
        "Testing the default"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/some/long/extended/path/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/some/long/extended/path/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'default'
        resolve_alias = False
        include_path = True
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         'default')

    def test_get_profile_name_else(self):
        "testing else statement in get_profile_name"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/some/long/extended/path/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/some/long/extended/path/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'foo'
        resolve_alias = False
        include_path = True
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         'foo')

    def test_naming_data_for_role_aws_arn(self):
        creds = GimmeAWSCreds()
        arn = 'arn:aws:iam::123456789012:role/Admin'
        d = creds._naming_data_for_role(arn)
        self.assertEqual(d['account'], '123456789012')
        self.assertEqual(d['role'], 'Admin')

    def test_naming_data_for_role_alicloud_ram(self):
        creds = GimmeAWSCreds()
        arn = 'acs:ram::111122223333:role/MyRole'
        d = creds._naming_data_for_role(arn)
        self.assertEqual(d['account'], '111122223333')
        self.assertEqual(d['role'], 'MyRole')
        self.assertEqual(d['path'], '/')


class TestCredProfilePrecedence(unittest.TestCase):
    """Tests for --aws-cred-profile CLI flag precedence over env var and config file.

    Expected precedence: CLI flag > env var > config file
    """

    CONFIG_TEMPLATE = """[DEFAULT]
client_id = test-client
okta_org_url = https://test.okta.com
cred_profile = {cred_profile}
"""

    def setUp(self):
        self._temp_dirs = []

    def tearDown(self):
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _build_and_generate(self, argv=None, environ=None, config_cred_profile='file-profile'):
        test_ui = MockUserInterface(
            argv=argv or [],
            environ=environ or {},
        )
        self._temp_dirs.append(test_ui.HOME)
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write(self.CONFIG_TEMPLATE.format(cred_profile=config_cred_profile))

        creds = GimmeAWSCreds(ui=test_ui)
        creds.generate_config()
        return creds

    def test_cli_flag_overrides_config_file(self):
        """--aws-cred-profile should override the cred_profile from config file"""
        creds = self._build_and_generate(
            argv=['gimme-aws-creds', '--aws-cred-profile', 'cli-profile'],
            config_cred_profile='file-profile',
        )
        self.assertEqual(creds.conf_dict['cred_profile'], 'cli-profile')

    def test_cli_flag_overrides_env_var(self):
        """--aws-cred-profile should override GIMME_AWS_CREDS_CRED_PROFILE env var"""
        creds = self._build_and_generate(
            argv=['gimme-aws-creds', '--aws-cred-profile', 'cli-profile'],
            environ={'GIMME_AWS_CREDS_CRED_PROFILE': 'env-profile'},
            config_cred_profile='file-profile',
        )
        self.assertEqual(creds.conf_dict['cred_profile'], 'cli-profile')

    def test_env_var_overrides_config_file_when_no_cli_flag(self):
        """Without --aws-cred-profile, GIMME_AWS_CREDS_CRED_PROFILE should override config file"""
        creds = self._build_and_generate(
            argv=['gimme-aws-creds'],
            environ={'GIMME_AWS_CREDS_CRED_PROFILE': 'env-profile'},
            config_cred_profile='file-profile',
        )
        self.assertEqual(creds.conf_dict['cred_profile'], 'env-profile')

    def test_config_file_used_when_no_cli_flag_or_env_var(self):
        """Without --aws-cred-profile or env var, config file value should be used"""
        creds = self._build_and_generate(
            argv=['gimme-aws-creds'],
            config_cred_profile='file-profile',
        )
        self.assertEqual(creds.conf_dict['cred_profile'], 'file-profile')


class TestGenerateConfigDebugLogging(unittest.TestCase):
    """Tests verifying GimmeAWSCreds.generate_config() emits the resolved
    configuration to the debug logger when --debug is set, with CLI/env
    overrides correctly attributed.
    """

    CONFIG_TEMPLATE = """[DEFAULT]
client_id = test-client
okta_org_url = https://test.okta.com
gimme_creds_server = appurl
"""

    def setUp(self):
        self._temp_dirs = []

    def tearDown(self):
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _build_ui(self, argv=None, environ=None, config_contents=None):
        test_ui = MockUserInterface(
            argv=argv or ['gimme-aws-creds'],
            environ=environ or {},
        )
        self._temp_dirs.append(test_ui.HOME)
        with open(test_ui.HOME + "/.okta_aws_login_config", "w") as f:
            f.write(config_contents if config_contents is not None
                    else self.CONFIG_TEMPLATE)
        return test_ui

    def test_no_debug_output_when_flag_absent(self):
        """generate_config does NOT emit RESOLVED CONFIGURATION without --debug."""
        test_ui = self._build_ui(argv=['gimme-aws-creds'])
        creds = GimmeAWSCreds(ui=test_ui)

        # Capture all DEBUG logs from gimme_aws_creds; none should be emitted.
        # assertNoLogs is available in Python 3.10+.
        with self.assertNoLogs('gimme_aws_creds', level='DEBUG'):
            creds.generate_config()

    def test_debug_flag_emits_resolved_configuration(self):
        """--debug should emit a 'RESOLVED CONFIGURATION' block at DEBUG level."""
        test_ui = self._build_ui(argv=['gimme-aws-creds', '--debug'])
        creds = GimmeAWSCreds(ui=test_ui)

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            creds.generate_config()

        full_output = '\n'.join(captured.output)
        self.assertIn('RESOLVED CONFIGURATION', full_output)
        self.assertIn('Configuration file:', full_output)
        self.assertIn('Active profile:', full_output)

    def test_debug_records_env_override(self):
        """Env vars in envvar_list show up tagged as env: <VAR>."""
        test_ui = self._build_ui(
            argv=['gimme-aws-creds', '--debug'],
            environ={'GIMME_AWS_CREDS_OUTPUT_FORMAT': 'json'},
        )
        creds = GimmeAWSCreds(ui=test_ui)

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            creds.generate_config()

        full_output = '\n'.join(captured.output)
        self.assertIn('env: GIMME_AWS_CREDS_OUTPUT_FORMAT', full_output)
        # And the conf_dict was actually overridden
        self.assertEqual(creds.conf_dict['output_format'], 'json')

    def test_debug_records_cli_override_for_cred_profile(self):
        """--aws-cred-profile shows up tagged as cli: --aws-cred-profile."""
        test_ui = self._build_ui(argv=[
            'gimme-aws-creds', '--debug',
            '--aws-cred-profile', 'cli-profile',
        ])
        creds = GimmeAWSCreds(ui=test_ui)

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            creds.generate_config()

        full_output = '\n'.join(captured.output)
        self.assertIn('cli: --aws-cred-profile', full_output)
        self.assertIn('cli-profile', full_output)
        self.assertEqual(creds.conf_dict['cred_profile'], 'cli-profile')

    def test_debug_records_disable_keychain_cli_override(self):
        """--disable-keychain shows up tagged as a CLI override on enable_keychain."""
        # The DEFAULT profile from CONFIG_TEMPLATE doesn't include enable_keychain;
        # main.py sets it to False when --disable-keychain is passed.
        test_ui = self._build_ui(argv=[
            'gimme-aws-creds', '--debug', '--disable-keychain',
        ])
        creds = GimmeAWSCreds(ui=test_ui)

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            creds.generate_config()

        full_output = '\n'.join(captured.output)
        self.assertIn('cli: --disable-keychain', full_output)

    def test_debug_does_not_leak_sensitive_env_values(self):
        """Sensitive env values (tokens, passwords) must be REDACTED in output."""
        test_ui = self._build_ui(
            argv=['gimme-aws-creds', '--debug'],
            environ={
                'OKTA_DEVICE_TOKEN': 'super-secret-token-1234567890',
                'OKTA_PASSWORD': 'my-secret-password',
            },
        )
        creds = GimmeAWSCreds(ui=test_ui)

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            creds.generate_config()

        full_output = '\n'.join(captured.output)
        # Raw secrets must not appear
        self.assertNotIn('super-secret-token-1234567890', full_output)
        self.assertNotIn('my-secret-password', full_output)
        # The mask marker should be present
        self.assertIn('[REDACTED]', full_output)

    def test_debug_output_includes_inheritance_chain(self):
        """When the active profile inherits, the chain is included in output."""
        config_contents = """
[mybase]
client_id = base-id
gimme_creds_server = appurl
okta_org_url = https://test.okta.com

[myprofile]
inherits = mybase
aws_appname = MyApp
"""
        test_ui = self._build_ui(
            argv=['gimme-aws-creds', '--debug', '--profile', 'myprofile'],
            config_contents=config_contents,
        )
        creds = GimmeAWSCreds(ui=test_ui)

        with self.assertLogs('gimme_aws_creds', level='DEBUG') as captured:
            creds.generate_config()

        full_output = '\n'.join(captured.output)
        self.assertIn('Inheritance chain:', full_output)
        self.assertIn('myprofile', full_output)
        self.assertIn('mybase', full_output)
        # Per-key sources reflect the owning profile
        self.assertIn('profile: mybase', full_output)
        self.assertIn('profile: myprofile', full_output)
