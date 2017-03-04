"""Unit tests for gimme_aws_creds.okta.OktaClient"""
import json
import unittest
import requests
from mock import patch
from nose.tools import (
    assert_equals,
    assert_dict_equal,
    assert_list_equal,
    assert_true
)

from gimme_aws_creds.okta import OktaClient

class TestOktaClient(unittest.TestCase):
    """Class to test Okta Client Class.
       Mock is used to mock external calls"""

    def setUp(self):
        """Set up for the unit tests"""
        self.okta_api_key = 'XXXXXX'
        self.idp_entry_url = 'https://example.okta.com'
        self.client = OktaClient(self.okta_api_key, self.idp_entry_url)
        self.login_resp = {
            "_embedded": {
                "user": {
                    "id": "00000",
                }
            },
            "status": "SUCCESS"
        }

    @staticmethod
    def _mock_response(status=200, reason='OK', content=''):
        mock_resp = requests.Response()
        mock_resp.status_code = status
        # Reason the status code occurred.
        mock_resp.reason = reason
        # Raw content in byte
        mock_resp._content = bytes(content.encode('utf-8'))
        return mock_resp

    def test_get_headers(self):
        """Testing that get_headers returns the expected results"""
        header = self.client.get_headers()
        assert_equals(header['Authorization'], 'SSWS XXXXXX')

    @patch('requests.post')
    def test_get_login_response(self, mock_post):
        """Testing login respose is returned as expected"""
        login = {
            "expiresAt":"2017-02-04T00:26:24.000Z",
            "status":"SUCCESS",
            "sessionToken":"20111ZTiraxruMoaA3cQh7RgG9lMqPiVk",
            "_embedded":{
                "user":{
                    "id":"00000",
                    "profile":{
                        "login":"Jane.Doe@example.com",
                        "firstName":"Jane",
                        "lastName":"Doe",
                        "locale":"en",
                        "timeZone":"America/Los_Angeles"
                    }
                }
            }
        }
        mock_post.return_value = self._mock_response(content=json.dumps(login))
        response = self.client.get_login_response("username", "password")
        assert_dict_equal(response, login)

    @patch('requests.get')
    def test_get_app_links(self, mock_get):
        """Testing correct response is returned from get_app_links"""
        app_links = [
            {
                "id":"1",
                "label":"AWS Prod",
                "linkUrl":"https://example.oktapreview.com/1"
            },
            {
                "id":"2",
                "label":"AWS Dev",
                "linkUrl":"https://example.oktapreview.com/2"
            }
        ]
        mock_resp = self._mock_response(content=json.dumps(app_links))
        mock_get.return_value = mock_resp
        response = self.client.get_app_links(self.login_resp)
        assert_list_equal(response, app_links)

    @patch('gimme_aws_creds.okta.OktaClient.get_app_links')
    @patch('builtins.input', return_value='0')
    def test_get_app(self, mock_input, mock_app_links):
        """Testing correct app was returned from get_app"""
        app_links = [
            {
                "id":"1",
                "label":"AWS Prod",
                "linkUrl":"https://example.oktapreview.com/1"
            },
            {
                "id":"2",
                "label":"AWS Dev",
                "linkUrl":"https://example.oktapreview.com/2"
            }
        ]

        # mock get_app_links response
        mock_app_links.return_value = app_links
        response = self.client.get_app(self.login_resp)

        # confirm the mock was called
        assert_true(mock_app_links.called)

        # confirm the correct apps were returned
        assert_equals(response, "AWS Prod")

    @patch('requests.get')
    @patch('builtins.input', return_value='1')
    def test_get_role(self, mock_input, mock_get):
        """Testing that get_role returns the correct role"""
        roles = [
            {
                "name": "amazon_aws",
                "label": "My AWS App",
                "status": "ACTIVE",
                "_embedded": {
                    "user":
                        {
                            "id": "000000",
                            "credentials":{
                                "userName": "joe.blow@example.com"
                            },
                            "profile":{
                                "samlRoles":["OktaAWSAdminRole", "OktaAWSReadOnlyRole"]
                            }
                        }
                    }
                }
            ]

        # mock response and status code
        mock_resp = self._mock_response(content=json.dumps(roles))
        mock_get.return_value = mock_resp
        response = self.client.get_role(self.login_resp, "My AWS App")

        # confirm that the correct role was returned
        assert_equals(response, "OktaAWSReadOnlyRole")

    @patch('requests.get')
    def test_get_idp_arn(self, mock_get):
        """Testing that get_idp_arn returns the correct ARN"""
        app_id = '1q2w3e4r5t'
        idp_arn_json = {
            "id": "1q2w3e4r5t",
            "settings": {
                "app": {
                    "accessKey": "QW08arTG",
                    "secretKey": "OPOJSDU1234",
                    "sessionDuration": 3600,
                    "identityProviderArn": "arn:aws:iam::0987654321:saml-provider/OktaIdP",
                    "awsEnvironmentType": "aws.amazon",
                    "loginURL": "https://cdt-test.signin.aws.amazon.com/console"
                }
            }
        }

        # mock the response
        mock_resp = self._mock_response(content=json.dumps(idp_arn_json))
        mock_get.return_value = mock_resp
        idp_arn = self.client.get_idp_arn(app_id)

        # confirm that self.idp_arn got set correctly
        assert_equals(idp_arn, 'arn:aws:iam::0987654321:saml-provider/OktaIdP')

    @patch('requests.get')
    @patch('gimme_aws_creds.okta.OktaClient.get_saml_assertion')
    def test_get_role_arn(self, mock_saml_assertion, mock_get):
        """Testing that get_role_arn returns the correct ARN"""
        # huge long ugly SAML
        saml = "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz48c2FtbDJwOlJlc3BvbnNlIHhtbG5zOnNhbWwycD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOnByb3RvY29sIiBEZXN0aW5hdGlvbj0iaHR0cHM6Ly9zaWduaW4uYXdzLmFtYXpvbi5jb20vc2FtbCIgSUQ9ImlkMSIgSXNzdWVJbnN0YW50PSIyMDE3LTAyLTA2VDIzOjM2OjM1Ljk0M1oiIFZlcnNpb249IjIuMCIgeG1sbnM6eHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIj48c2FtbDI6SXNzdWVyIHhtbG5zOnNhbWwyPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXNzZXJ0aW9uIiBGb3JtYXQ9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpuYW1laWQtZm9ybWF0OmVudGl0eSI+aHR0cDovL3d3dy5va3RhLmNvbS9leDwvc2FtbDI6SXNzdWVyPjxkczpTaWduYXR1cmUgeG1sbnM6ZHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvMDkveG1sZHNpZyMiPjxkczpTaWduZWRJbmZvPjxkczpDYW5vbmljYWxpemF0aW9uTWV0aG9kIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS8xMC94bWwtZXhjLWMxNG4jIi8+PGRzOlNpZ25hdHVyZU1ldGhvZCBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMDQveG1sZHNpZy1tb3JlI3JzYS1zaGEyNTYiLz48ZHM6UmVmZXJlbmNlIFVSST0iI2lkMSI+PGRzOlRyYW5zZm9ybXM+PGRzOlRyYW5zZm9ybSBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvMDkveG1sZHNpZyNlbnZlbG9wZWQtc2lnbmF0dXJlIi8+PGRzOlRyYW5zZm9ybSBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMTAveG1sLWV4Yy1jMTRuIyI+PGVjOkluY2x1c2l2ZU5hbWVzcGFjZXMgeG1sbnM6ZWM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMTAveG1sLWV4Yy1jMTRuIyIgUHJlZml4TGlzdD0ieHMiLz48L2RzOlRyYW5zZm9ybT48L2RzOlRyYW5zZm9ybXM+PGRzOkRpZ2VzdE1ldGhvZCBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMDQveG1sZW5jI3NoYTI1NiIvPjxkczpEaWdlc3RWYWx1ZT4xPC9kczpEaWdlc3RWYWx1ZT48L2RzOlJlZmVyZW5jZT48L2RzOlNpZ25lZEluZm8+PGRzOlNpZ25hdHVyZVZhbHVlPjE8L2RzOlNpZ25hdHVyZVZhbHVlPjxkczpLZXlJbmZvPjxkczpYNTA5RGF0YT48ZHM6WDUwOUNlcnRpZmljYXRlPjENCjwvZHM6WDUwOUNlcnRpZmljYXRlPjwvZHM6WDUwOURhdGE+PC9kczpLZXlJbmZvPjwvZHM6U2lnbmF0dXJlPjxzYW1sMnA6U3RhdHVzIHhtbG5zOnNhbWwycD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOnByb3RvY29sIj48c2FtbDJwOlN0YXR1c0NvZGUgVmFsdWU9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpzdGF0dXM6U3VjY2VzcyIvPjwvc2FtbDJwOlN0YXR1cz48c2FtbDI6QXNzZXJ0aW9uIHhtbG5zOnNhbWwyPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXNzZXJ0aW9uIiBJRD0iaWQxIiBJc3N1ZUluc3RhbnQ9IjIwMTctMDItMDZUMjM6MzY6MzUuOTQzWiIgVmVyc2lvbj0iMi4wIiB4bWxuczp4cz0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEiPjxzYW1sMjpJc3N1ZXIgRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6bmFtZWlkLWZvcm1hdDplbnRpdHkiIHhtbG5zOnNhbWwyPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXNzZXJ0aW9uIj5odHRwOi8vd3d3Lm9rdGEuY29tLzE8L3NhbWwyOklzc3Vlcj48ZHM6U2lnbmF0dXJlIHhtbG5zOmRzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjIj48ZHM6U2lnbmVkSW5mbz48ZHM6Q2Fub25pY2FsaXphdGlvbk1ldGhvZCBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMTAveG1sLWV4Yy1jMTRuIyIvPjxkczpTaWduYXR1cmVNZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGRzaWctbW9yZSNyc2Etc2hhMjU2Ii8+PGRzOlJlZmVyZW5jZSBVUkk9IiNpZDEiPjxkczpUcmFuc2Zvcm1zPjxkczpUcmFuc2Zvcm0gQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjZW52ZWxvcGVkLXNpZ25hdHVyZSIvPjxkczpUcmFuc2Zvcm0gQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzEwL3htbC1leGMtYzE0biMiPjxlYzpJbmNsdXNpdmVOYW1lc3BhY2VzIHhtbG5zOmVjPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzEwL3htbC1leGMtYzE0biMiIFByZWZpeExpc3Q9InhzIi8+PC9kczpUcmFuc2Zvcm0+PC9kczpUcmFuc2Zvcm1zPjxkczpEaWdlc3RNZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGVuYyNzaGEyNTYiLz48ZHM6RGlnZXN0VmFsdWU+MTwvZHM6RGlnZXN0VmFsdWU+PC9kczpSZWZlcmVuY2U+PC9kczpTaWduZWRJbmZvPjxkczpTaWduYXR1cmVWYWx1ZT4xPC9kczpTaWduYXR1cmVWYWx1ZT48ZHM6S2V5SW5mbz48ZHM6WDUwOURhdGE+PGRzOlg1MDlDZXJ0aWZpY2F0ZT4NCjE8L2RzOlg1MDlDZXJ0aWZpY2F0ZT48L2RzOlg1MDlEYXRhPjwvZHM6S2V5SW5mbz48L2RzOlNpZ25hdHVyZT48c2FtbDI6U3ViamVjdCB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI+PHNhbWwyOk5hbWVJRCBGb3JtYXQ9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpuYW1laWQtZm9ybWF0OnVuc3BlY2lmaWVkIj5yYWluYm93QHVuaWNvcm4uY29tPC9zYW1sMjpOYW1lSUQ+PHNhbWwyOlN1YmplY3RDb25maXJtYXRpb24gTWV0aG9kPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6Y206YmVhcmVyIj48c2FtbDI6U3ViamVjdENvbmZpcm1hdGlvbkRhdGEgTm90T25PckFmdGVyPSIyMDE3LTAyLTA2VDIzOjQxOjM1Ljk0M1oiIFJlY2lwaWVudD0iaHR0cHM6Ly9zaWduaW4uYXdzLmFtYXpvbi5jb20vc2FtbCIvPjwvc2FtbDI6U3ViamVjdENvbmZpcm1hdGlvbj48L3NhbWwyOlN1YmplY3Q+PHNhbWwyOkNvbmRpdGlvbnMgTm90QmVmb3JlPSIyMDE3LTAyLTA2VDIzOjMxOjM1Ljk0M1oiIE5vdE9uT3JBZnRlcj0iMjAxNy0wMi0wNlQyMzo0MTozNS45NDNaIiB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI+PHNhbWwyOkF1ZGllbmNlUmVzdHJpY3Rpb24+PHNhbWwyOkF1ZGllbmNlPnVybjphbWF6b246d2Vic2VydmljZXM8L3NhbWwyOkF1ZGllbmNlPjwvc2FtbDI6QXVkaWVuY2VSZXN0cmljdGlvbj48L3NhbWwyOkNvbmRpdGlvbnM+PHNhbWwyOkF1dGhuU3RhdGVtZW50IEF1dGhuSW5zdGFudD0iMjAxNy0wMi0wNlQyMzozNjozNS45NDNaIiBTZXNzaW9uSW5kZXg9ImlkMTQ4NjQyNDE5NTk0My4xNjMwOTUwNDUxIiB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI+PHNhbWwyOkF1dGhuQ29udGV4dD48c2FtbDI6QXV0aG5Db250ZXh0Q2xhc3NSZWY+dXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFjOmNsYXNzZXM6UGFzc3dvcmRQcm90ZWN0ZWRUcmFuc3BvcnQ8L3NhbWwyOkF1dGhuQ29udGV4dENsYXNzUmVmPjwvc2FtbDI6QXV0aG5Db250ZXh0Pjwvc2FtbDI6QXV0aG5TdGF0ZW1lbnQ+PHNhbWwyOkF0dHJpYnV0ZVN0YXRlbWVudCB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI+PHNhbWwyOkF0dHJpYnV0ZSBOYW1lPSJodHRwczovL2F3cy5hbWF6b24uY29tL1NBTUwvQXR0cmlidXRlcy9Sb2xlIiBOYW1lRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXR0cm5hbWUtZm9ybWF0OnVyaSI+PHNhbWwyOkF0dHJpYnV0ZVZhbHVlIHhtbG5zOnhzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYSIgeG1sbnM6eHNpPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYS1pbnN0YW5jZSIgeHNpOnR5cGU9InhzOnN0cmluZyI+YXJuOmF3czppYW06OjA5ODc2NTQzMjE6c2FtbC1wcm92aWRlci9Pa3RhSWRQLGFybjphd3M6aWFtOjowOTg3NjU0MzIxOnJvbGUvT2t0YUFXU0FkbWluUm9sZTwvc2FtbDI6QXR0cmlidXRlVmFsdWU+PHNhbWwyOkF0dHJpYnV0ZVZhbHVlIHhtbG5zOnhzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYSIgeG1sbnM6eHNpPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYS1pbnN0YW5jZSIgeHNpOnR5cGU9InhzOnN0cmluZyI+YXJuOmF3czppYW06OjA5ODc2NTQzMjE6c2FtbC1wcm92aWRlci9Pa3RhSWRQLGFybjphd3M6aWFtOjowOTg3NjU0MzIxOnJvbGUvT2t0YUFXU1JlYWRPbmx5Um9sZTwvc2FtbDI6QXR0cmlidXRlVmFsdWU+PC9zYW1sMjpBdHRyaWJ1dGU+PHNhbWwyOkF0dHJpYnV0ZSBOYW1lPSJodHRwczovL2F3cy5hbWF6b24uY29tL1NBTUwvQXR0cmlidXRlcy9Sb2xlU2Vzc2lvbk5hbWUiIE5hbWVGb3JtYXQ9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphdHRybmFtZS1mb3JtYXQ6YmFzaWMiPjxzYW1sMjpBdHRyaWJ1dGVWYWx1ZSB4bWxuczp4cz0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEiIHhtbG5zOnhzaT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEtaW5zdGFuY2UiIHhzaTp0eXBlPSJ4czpzdHJpbmciPnJhaW5ib3dAdW5pY29ybi5jb208L3NhbWwyOkF0dHJpYnV0ZVZhbHVlPjwvc2FtbDI6QXR0cmlidXRlPjxzYW1sMjpBdHRyaWJ1dGUgTmFtZT0iaHR0cHM6Ly9hd3MuYW1hem9uLmNvbS9TQU1ML0F0dHJpYnV0ZXMvU2Vzc2lvbkR1cmF0aW9uIiBOYW1lRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXR0cm5hbWUtZm9ybWF0OmJhc2ljIj48c2FtbDI6QXR0cmlidXRlVmFsdWUgeG1sbnM6eHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIiB4bWxuczp4c2k9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hLWluc3RhbmNlIiB4c2k6dHlwZT0ieHM6c3RyaW5nIj4zNjAwPC9zYW1sMjpBdHRyaWJ1dGVWYWx1ZT48L3NhbWwyOkF0dHJpYnV0ZT48L3NhbWwyOkF0dHJpYnV0ZVN0YXRlbWVudD48L3NhbWwyOkFzc2VydGlvbj48L3NhbWwycDpSZXNwb25zZT4="
        fake_response = "FAKE"

        # set the response from the get. it doens't matter what it is
        # since the saml response is mocked
        mock_resp = self._mock_response(content=fake_response)
        mock_get.return_value = mock_resp

        # set the saml response
        mock_saml_assertion.return_value = saml

        role_arn = self.client.get_role_arn(
            "https://example.okta.com/blah",
            "TOKEN",
            "OktaAWSAdminRole"
        )

        # confirm that the correct ARN got set
        assert_equals(role_arn, 'arn:aws:iam::0987654321:role/OktaAWSAdminRole')
