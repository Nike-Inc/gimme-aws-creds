# Stuff for tests...
from unittest.mock import Mock, patch, MagicMock
from nose.tools import raises, assert_raises, assert_equals, assert_dict_equal, assert_list_equal, assert_true, assert_is_none

# other stuff
import json
from requests.exceptions import HTTPError

# Local imports...
from CerberusMiniClient import CerberusMiniClient

class TestCerberusClient(object):

    @classmethod
    @patch('CerberusMiniClient.CerberusMiniClient.set_token', return_value='1234-asdf-1234hy-qwer6')
    def setup_class(self, mock_token):
        self.client = CerberusMiniClient('testuser', 'hardtoguesspasswd')

    """
    modeled after https://goo.gl/WV2WGe
    """
    def _mock_response(
            self,
            status=200,
            content="SUTFF",
            json_data=None,
            text="""{"key": "value"}""",
            raise_for_status=None):

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        if raise_for_status:
            mock_resp.raise_for_status.side_effect = raise_for_status
        mock_resp.status_code = status
        mock_resp.content = content
        mock_resp.text = text
        # add json data if provided
        if json_data:
            mock_resp.json = mock.Mock(
                return_value=json_data
            )
        return mock_resp


    def test_username(self):
        assert_equals(self.client.username, 'testuser')

    def test_get_token(self):
        token = self.client.get_token()
        assert_equals(token, self.client.token)

    @patch('requests.get')
    def test_get_auth(self, mock_get):
        auth_resp = """{"status": "mfa_req", "data":
                        {"username": "unicorn@rainbow.com",
                        "state_token": "0127a384d305138d4e",
                        "client_token": "None", "user_id": "1325",
                        "devices": [{"id": "223", "name":
                        "Google Authenticator"}]}}"""

        # mock return response
        mock_resp = self._mock_response(text=auth_resp)
        mock_get.return_value = mock_resp

        response = self.client.get_auth()

        # confirm response matches the mock
        assert_dict_equal(response, json.loads(auth_resp))

    @raises(HTTPError)
    @patch('requests.get')
    def test_when_not_200_status_code(self, mock_get):
        mock_resp = self._mock_response(status=404, raise_for_status=HTTPError("google is down"))
        mock_get.return_value = mock_resp
        self.client.get_auth()


    def test_mfa(self):
        print("hello world")
