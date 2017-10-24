import unittest

from mock import patch

from gimme_aws_creds.main import GimmeAWSCreds


class TestMain(unittest.TestCase):
    APP_INFO = {
        'roles': [
            {'name': 'test1'},
            {'name': 'test2'}
        ]
    }

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
        self.assertEqual(selection, self.APP_INFO['roles'][0])

        selection = creds._choose_app(self.AWS_INFO)
        self.assertEqual(selection, self.AWS_INFO[0])

    @patch('builtins.input', return_value='1')
    def test_choose_role_app_1(self, mock):
        creds = GimmeAWSCreds()
        selection = creds._choose_role(self.APP_INFO)
        self.assertEqual(selection, self.APP_INFO['roles'][1])

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
