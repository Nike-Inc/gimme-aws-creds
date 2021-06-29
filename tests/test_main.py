import unittest

from mock import patch

from gimme_aws_creds import errors
from gimme_aws_creds.main import GimmeAWSCreds
from gimme_aws_creds.common import RoleSet


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

        self.assertRaises(errors.GimmeAWSCredsExitBase, creds._get_partition_from_saml_acs, 'https://signin.amazonaws-foo.com/saml')
