# Standard library imports...
from unittest.mock import Mock, patch

# Third-party imports...
from nose.tools import assert_equals
import argparse
import getpass

# Local imports...
from gimme_aws_creds import GimmeAWSCreds

class TestGimmeAWSCreds(object):

    @classmethod
    def setup_class(self):
        self.gac = GimmeAWSCreds()
        self.gac.okta_api_key = 'XXXXXX'

    def test_get_headers(self):
        header = self.gac.get_headers()
        print (header['Authorization'])
        assert_equals(header['Authorization'], 'SSWS XXXXXX')

    @patch('argparse.ArgumentParser.parse_args',
            return_value=argparse.Namespace(username='ann', configure=False))
    def test_get_args_username(self,mock_args):
        self.gac.get_args()
        assert_equals(self.gac.username, 'ann')

    @patch('getpass.getpass', return_value='1234qwert')
    def test_get_user_creds(self,mock_input):
        self.gac.get_user_creds()
        assert_equals(self.gac.password, '1234qwert')
