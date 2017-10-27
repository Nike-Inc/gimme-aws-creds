import unittest

from mock import patch

from gimme_aws_creds.main import GimmeAWSCreds, RoleSet


class TestMain(unittest.TestCase):
    APP_INFO = [
        RoleSet(idp='idp', role='test1'),
        RoleSet(idp='idp', role='test2')
    ]

    AWS_INFO = [
        {'name': 'test1'},
        {'name': 'test2'}
    ]

    @patch('builtins.input', return_value='-1')
    def test_choose_role_app_neg1(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(SystemExit, creds._choose_role, self.APP_INFO)
        self.assertRaises(SystemExit, creds._choose_app, self.AWS_INFO)

    @patch('builtins.input', return_value='0')
    def test_choose_role_app_0(self, mock):
        creds = GimmeAWSCreds()
        selection = creds._choose_role(self.APP_INFO)
        self.assertEqual(selection, self.APP_INFO[0].role)

        selection = creds._choose_app(self.AWS_INFO)
        self.assertEqual(selection, self.AWS_INFO[0])

    @patch('builtins.input', return_value='1')
    def test_choose_role_app_1(self, mock):
        creds = GimmeAWSCreds()
        selection = creds._choose_role(self.APP_INFO)
        self.assertEqual(selection, self.APP_INFO[1].role)

        selection = creds._choose_app(self.AWS_INFO)
        self.assertEqual(selection, self.AWS_INFO[1])

    @patch('builtins.input', return_value='2')
    def test_choose_role_app_2(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(SystemExit, creds._choose_role, self.APP_INFO)
        self.assertRaises(SystemExit, creds._choose_app, self.AWS_INFO)

    @patch('builtins.input', return_value='a')
    def test_choose_role_app_a(self, mock):
        creds = GimmeAWSCreds()
        self.assertRaises(SystemExit, creds._choose_role, self.APP_INFO)
        self.assertRaises(SystemExit, creds._choose_app, self.AWS_INFO)

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

    def test_get_selected_role_from_config_0(self):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_role('test1', self.APP_INFO)
        self.assertEqual(selection, 'test1')

    def test_get_selected_role_from_config_1(self):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_role('test2', self.APP_INFO)
        self.assertEqual(selection, 'test2')

    def test_get_selected_role_all(self):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_role('all', self.APP_INFO)
        self.assertEqual(selection, 'all')

    @patch('builtins.input', return_value='0')
    def test_missing_role_from_config(self, mock):
        creds = GimmeAWSCreds()

        selection = creds._get_selected_role('test3', self.APP_INFO)
        self.assertEqual(selection, 'test1')

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

        self.assertRaises(SystemExit, creds._get_partition_from_saml_acs, 'https://signin.amazonaws-foo.com/saml')
