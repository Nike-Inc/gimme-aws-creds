# Stuff for tests...
from unittest.mock import Mock, patch, MagicMock
from nose.tools import assert_equals, assert_dict_equal, assert_list_equal, assert_true

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
        self.gac.aws_appname = "My AWS App"
        self.gac.okta_api_key = 'XXXXXX'
        self.gac.idp_entry_url = 'https://example.okta.com'
        self.maxDiff = None
        self.login_resp =     login_resp = {
                            "_embedded": {
                                "user": {
                                    "id": "00000",
                                }
                            },
                            "status": "SUCCESS"
                        }

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
        login = """{"expiresAt":"2017-02-04T00:26:24.000Z", "status":"SUCCESS",
                    "sessionToken":"20111ZTiraxruMoaA3cQh7RgG9lMqPiVk",
                    "_embedded":{"user":{"id":"00000",
                    "profile":{"login":"Jane.Doe@example.com", "firstName":"Jane",
                    "lastName":"Doe", "locale":"en","timeZone":"America/Los_Angeles"}}}}"""
        mock_post.return_value = Mock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = login
        response = self.gac.get_login_response()
        assert_dict_equal(response, json.loads(login))

    @patch('requests.get')
    def test_get_app_links(self,mock_get):
        app_links = """[{"id":"1","label":"AWS Prod","linkUrl":"https://example.oktapreview.com/1"},
                       {"id":"2","label":"AWS Dev","linkUrl":"https://example.oktapreview.com/2"}]"""
        mock_get.return_value = Mock()
        mock_get.return_value.text = app_links
        response = self.gac.get_app_links(self.login_resp)
        assert_list_equal(response, json.loads(app_links))

    @patch('gimme_aws_creds.GimmeAWSCreds.get_app_links')
    @patch('builtins.input', return_value='0')
    def test_get_app(self,mock_input,mock_app_links):
        app_links = [{"id":"1","label":"AWS Prod","linkUrl":"https://example.oktapreview.com/1"},
                       {"id":"2","label":"AWS Dev","linkUrl":"https://example.oktapreview.com/2"}]

        # mock get_app_links response
        mock_app_links.return_value = Mock()
        mock_app_links.return_value = app_links
        response = self.gac.get_app(self.login_resp)

        # confirm the mock was called
        assert_true(mock_app_links.called)

        # confirm the correct apps were returned
        assert_equals(response, "AWS Prod")

    @patch('requests.get')
    @patch('builtins.input', return_value='1')
    def test_get_role(self,mock_input,mock_get):
        roles = """[ { "name": "amazon_aws", "label": "My AWS App",
                    "status": "ACTIVE", "_embedded": { "user":
                    { "id": "000000", "credentials":
                    { "userName": "joe.blow@example.com" }, "profile":
                    { "samlRoles": [ "OktaAWSAdminRole", "OktaAWSReadOnlyRole" ] } } } } ]"""

        # mock response and status code
        mock_get.return_value = Mock()
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = roles
        response = self.gac.get_role(self.login_resp)

        # confirm that the correct role was returned
        assert_equals(response, "OktaAWSReadOnlyRole")

    @patch('requests.get')
    def test_set_idp_arn(self,mock_get):
        app_id = '1q2w3e4r5t'
        idp_arn = """{
                      "id": "1q2w3e4r5t",
                      "settings": {
                        "app": {
                          "accessKey": null,
                          "secretKey": null,
                          "sessionDuration": 3600,
                          "identityProviderArn": "arn:aws:iam::0987654321:saml-provider/OktaIdP",
                          "awsEnvironmentType": "aws.amazon",
                          "loginURL": "https://cdt-test.signin.aws.amazon.com/console"
                        }
                      }
                    }"""

        # mock the response
        mock_get.return_value = Mock()
        mock_get.return_value.text = idp_arn
        response = self.gac.set_idp_arn(app_id)

        # confirm that self.idp_arn got set correctly
        assert_equals(self.gac.idp_arn, 'arn:aws:iam::0987654321:saml-provider/OktaIdP')
