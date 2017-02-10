# Stuff for tests...
from unittest.mock import Mock, patch, MagicMock
from nose.tools import assert_equals, assert_dict_equal, assert_list_equal, assert_true, assert_is_none

# other stuff

# Local imports...
from CerberusMiniClient import CerberusMiniClient

class TestCerberusClient(object):

    @classmethod
    @patch('CerberusMiniClient.CerberusMiniClient.set_token', return_value='1234-asdf-1234hy-qwer6')
    def setup_class(self, mock_token):
        self.client = CerberusMiniClient('testuser', 'hardtoguesspasswd')


    def test_username(self):
        assert_equals(self.client.username, 'testuser')

    def test_get_token(self):
        token = self.client.get_token()
        assert_equals(token, self.client.token)

    @patch('requests.get')
    def test_get_auth(self, mock_get):
        auth_resp = """{u'status': u'mfa_req', u'data':
                        {u'username': u'unicorn@rainbow.com',
                        u'state_token': u'0127a384d305138d4e3',
                        u'client_token': None, u'user_id': u'1325',
                        u'devices': [{u'id': u'223', u'name':
                        u'Google Authenticator'}]}}"""
        mock_get.return_value = Mock()
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = auth_resp

        response = self.client.get_auth()

        assert_list_equal(response, auth_resp)
