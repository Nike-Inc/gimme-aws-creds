# Stuff for tests...
from unittest.mock import Mock, patch, MagicMock
from nose.tools import assert_equals, assert_dict_equal

# other stuff
import argparse
import getpass
import json

# Local imports...
from gimme_aws_creds import GimmeAWSCreds

class TestGimmeAWSCreds(object):

    @classmethod
    def setup_class(self):
        self.gac = GimmeAWSCreds()
        self.gac.okta_api_key = 'XXXXXX'
        self.gac.idp_entry_url = 'https://example.okta.com'
        self.maxDiff = None

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
    def test_get_password(self,mock_input):
        self.gac.get_user_creds()
        assert_equals(self.gac.password, '1234qwert')

    @patch('requests.post')
    def test_get_login_response(self,mock_post):
        login = '{"expiresAt":"2017-02-04T00:26:24.000Z", "status":"SUCCESS", "sessionToken":"20111ZTiraxruM-0S_nbP3KoaY6nzSVaDYkBoaA3cQh7RgG9lMqPiVk", "_embedded":{"user":{"id":"00u937qp9ym9stuhL0h7", "profile":{"login":"Ann.Wallace@nike.com", "firstName":"Ann","lastName":"Wallace", "locale":"en","timeZone":"America/Los_Angeles"}}}}'
        mock_post.return_value = Mock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = login
        response = self.gac.get_login_response()
        assert_dict_equal(response, json.loads(login))
