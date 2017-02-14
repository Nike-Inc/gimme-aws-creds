# Stuff for tests...
from unittest.mock import Mock, patch, MagicMock
from nose.tools import raises, assert_equals, assert_dict_equal

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
        self.auth_resp = """{"status": "mfa_req", "data":
                        {"username": "unicorn@rainbow.com",
                        "state_token": "0127a384d305138d4e",
                        "client_token": "None", "user_id": "1325",
                        "devices": [{"id": "223", "name":
                        "Google Authenticator"}]}}"""

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
        # mock return response
        mock_resp = self._mock_response(text=self.auth_resp)
        mock_get.return_value = mock_resp
        response = self.client.get_auth()

        # confirm response matches the mock
        assert_dict_equal(response, json.loads(self.auth_resp))

    @raises(HTTPError)
    @patch('requests.get')
    def test_when_not_200_status_code(self, mock_get):
        mock_resp = self._mock_response(status=404, raise_for_status=HTTPError("google is down"))
        mock_get.return_value = mock_resp
        self.client.get_auth()

    @patch('builtins.input', return_value='0987654321')
    @patch('requests.post')
    def test_mfa_response(self,mock_post,mock_input):
        mfa_data =""" {
                      "status" : "success",
                      "data" : {
                        "user_id" : "134",
                        "username" : "unicorn@rainbow.com",
                        "state_token" : null,
                        "devices" : [ ],
                        "client_token" : {
                          "client_token" : "61e3-f3f-6536-a3e6-b498161d",
                          "policies" : [ "cloud-events-owner", "pixie-dust-owner"],
                          "metadata" : {
                            "groups" : "Rainbow.Playgroun.User,CareBear.users",
                            "is_admin" : "false",
                            "username" : "unicorn@rainbow.com"
                          },
                          "lease_duration" : 3600,
                          "renewable" : true
                        }
                      }
                    }"""
        # mock all the things
        mock_post.return_value = Mock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = mfa_data

        response = self.client.get_mfa(json.loads(self.auth_resp))

        # confirm the json matches
        assert_dict_equal(response, json.loads(mfa_data))

    @patch('requests.get')
    def test_get_sdb_id(self,mock_get):
        sdb_data = """[{
                 "id" : "5f0-99-414-bc-e5909c",
                 "name" : "Disco Events",
                 "path" : "app/disco-events/",
                 "category_id" : "b07-42d0-e6-9-0a47c03" },
                 {
                  "id" : "a7192aa7-83f0-45b7-91fb-f6b0eb",
                  "name" : "snowflake",
                  "path" : "app/snowflake/",
                  "category_id" : "b042d0-e6-90-0aec03"}]"""

        # don't mock me!
        mock_resp = self._mock_response(text=sdb_data)
        mock_get.return_value = mock_resp

        id = self.client.get_sdb_id("snowflake")
        sdb_json = json.loads(sdb_data)

        # confirm the id matches
        assert_equals(id, sdb_json[1]['id'])


    @patch('CerberusMiniClient.CerberusMiniClient.get_sdb_id',
            return_value="5f0-99-414-bc-e5909c")
    @patch('requests.get')
    def test_get_sdb_path(self,mock_get,mock_sdb_id):
        sdb_data = """{
                    "id" : "5f0-99-414-bc-e5909c",
                    "name" : "Disco Events",
                    "description" : "Studio 54",
                    "path" : "app/disco-events/" }"""
        mock_resp = self._mock_response(text=sdb_data)
        mock_get.return_value = mock_resp

        path = self.client.get_sdb_path("Disco Events")
        sdb_json = json.loads(sdb_data)

        assert_equals(path, sdb_json['path'])

    @patch('requests.get')
    def test_get_sdb_keys(self,mock_get):
        list_data = """{
                        "lease_id":"","renewable":false,"lease_duration":0,
                        "data":{"keys":["magic","princess"]},
                         "wrap_info":null,"warnings":null,"auth":null }"""
        mock_resp = self._mock_response(text=list_data)
        mock_get.return_value = mock_resp

        keys = self.client.get_sdb_keys('fake/path')

        # check that the first key is magic!
        assert_equals(keys[0], 'magic')

    @patch('requests.get')
    def test_getting_a_secret(self,mock_get):
        secret_data = """{
                        "data":{
                            "mykey": "mysecretdata",
                            "myotherkey": "moretopsecretstuff"
                        }}"""
        mock_resp = self._mock_response(text=secret_data)
        mock_get.return_value = mock_resp

        secret = self.client.get_secret('fake/path', 'myotherkey')

        # check to make sure we got the right secret
        assert_equals(secret, 'moretopsecretstuff')
