import unittest
from unittest.mock import patch

from gimme_aws_creds import errors
from gimme_aws_creds.common import RoleSet
from gimme_aws_creds.main import GimmeAWSCreds


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

    @patch('builtins.input', return_value='a')
    def test_choose_roles_app_a(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_roles, self.APP_INFO)
        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._choose_app, self.AWS_INFO)

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

        partition = creds._get_partition_from_saml_acs('https://signin.aws.amazon.com/saml')
        self.assertEqual(partition, 'aws')

    def test_get_partition_china(self):
        creds = GimmeAWSCreds()

        partition = creds._get_partition_from_saml_acs('https://signin.amazonaws.cn/saml')
        self.assertEqual(partition, 'aws-cn')

    def test_get_partition_govcloud(self):
        creds = GimmeAWSCreds()

        partition = creds._get_partition_from_saml_acs('https://signin.amazonaws-us-gov.com/saml')
        self.assertEqual(partition, 'aws-us-gov')

    def test_get_partition_unkown(self):
        creds = GimmeAWSCreds()

        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._get_partition_from_saml_acs,
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
        resolve_alias = 'True'
        include_path = 'False'
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
        resolve_alias = 'False'
        include_path = 'False'
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
        resolve_alias = 'False'
        include_path = 'True'
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
        resolve_alias = 'False'
        include_path = 'True'
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         'administrator')

    def test_get_profile_name_default(self):
        "Testing the default"
        creds = GimmeAWSCreds()
        naming_data = {'account': '123456789012', 'role': 'administrator', 'path': '/some/long/extended/path/'}
        role = RoleSet(idp='arn:aws:iam::123456789012:saml-provider/my-okta-provider',
                       role='arn:aws:iam::123456789012:role/some/long/extended/path/administrator',
                       friendly_account_name='Account: my-org-master (123456789012)',
                       friendly_role_name='administrator/administrator')
        cred_profile = 'default'
        resolve_alias = 'False'
        include_path = 'True'
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
        resolve_alias = 'False'
        include_path = 'True'
        self.assertEqual(creds.get_profile_name(cred_profile, include_path, naming_data, resolve_alias, role),
                         'foo')
