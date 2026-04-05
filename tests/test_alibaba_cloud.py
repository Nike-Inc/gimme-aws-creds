"""Unit tests for gimme_aws_creds.alibaba_cloud"""
import base64
import json
import re
import unittest
from unittest.mock import MagicMock, patch

import requests
import responses

from gimme_aws_creds import errors
from gimme_aws_creds.alibaba_cloud import AlibabaCloudClient, AlibabaCloudRoleSet, enumerate_saml_roles


def _b64_xml(xml_str):
    return base64.b64encode(xml_str.encode('utf-8')).decode('ascii')


ALIBABA_CLOUD_ASSERTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Assertion xmlns="urn:oasis:names:tc:SAML:2.0:assertion">
  <AttributeStatement>
    <Attribute Name="https://www.aliyun.com/SAML-Role/Attributes/Role">
      <AttributeValue>acs:ram::111122223333:role/Admin,acs:ram::111122223333:saml-provider/Okta</AttributeValue>
    </Attribute>
  </AttributeStatement>
</Assertion>"""

ALIBABA_CLOUD_ASSERTION_MULTI = """<?xml version="1.0" encoding="UTF-8"?>
<Assertion xmlns="urn:oasis:names:tc:SAML:2.0:assertion">
  <AttributeStatement>
    <Attribute Name="https://www.aliyun.com/SAML-Role/Attributes/Role">
      <AttributeValue>acs:ram::111122223333:role/R1,acs:ram::111122223333:saml-provider/P1</AttributeValue>
      <AttributeValue>acs:ram::444455556666:role/R2,acs:ram::444455556666:saml-provider/P2</AttributeValue>
    </Attribute>
  </AttributeStatement>
</Assertion>"""


class TestAlibabaCloudClient(unittest.TestCase):
    """Tests for AlibabaCloudClient."""

    def setUp(self):
        self.okta_org_url = 'https://example-oie.okta.com'
        self.client_id = '00Wf8xZJ79mSoTY'
        self.session = requests.Session()
        self.client = AlibabaCloudClient(self.session, self.okta_org_url, self.client_id, verify_ssl_certs=False)
        self.saml_app_url = 'https://example-oie.okta.com/app/alicloud/exk1234567890/sso/saml'
        self.auth_session = {
            'access_token': 'at',
            'id_token': 'idt',
        }
        self.interclient_response = {
            'token_type': 'Bearer',
            'expires_in': 300,
            'access_token': 'interclient-access-token',
            'issued_token_type': 'urn:okta:params:oauth:token-type:interclient_token',
        }

    def test_http_client_must_be_session(self):
        with self.assertRaises(errors.GimmeAWSCredsError):
            AlibabaCloudClient(object(), self.okta_org_url, self.client_id)

    @responses.activate
    def test_interclient_token_exchange_success(self):
        responses.add(
            responses.POST,
            self.okta_org_url + '/oauth2/v1/token',
            status=200,
            body=json.dumps(self.interclient_response),
        )
        out = self.client._interclient_token_exchange('exk1234567890', 'at', 'idt')
        self.assertEqual(out, self.interclient_response)

    @responses.activate
    def test_interclient_token_exchange_400(self):
        err = {'error': 'invalid_grant', 'error_description': 'bad'}
        responses.add(
            responses.POST,
            self.okta_org_url + '/oauth2/v1/token',
            status=400,
            body=json.dumps(err),
        )
        with self.assertRaises(errors.GimmeAWSCredsError) as ctx:
            self.client._interclient_token_exchange('exk1234567890', 'at', 'idt')
        self.assertIn('Interclient token exchange', ctx.exception.message)

    @responses.activate
    def test_interclient_token_exchange_invalid_json(self):
        responses.add(
            responses.POST,
            self.okta_org_url + '/oauth2/v1/token',
            status=200,
            body='not json',
        )
        with self.assertRaises(errors.GimmeAWSCredsError) as ctx:
            self.client._interclient_token_exchange('exk1234567890', 'at', 'idt')
        self.assertIn('Invalid JSON', ctx.exception.message)

    @responses.activate
    def test_get_saml_response_success(self):
        html = """<html><body><form action="https://signin.aliyun.com/saml">
<input name="SAMLResponse" type="hidden" value="PHhtbC8+"/>
<input name="RelayState" type="hidden" value="rs"/>
</form></body></html>"""
        responses.add(
            responses.POST,
            self.okta_org_url + '/oauth2/v1/token',
            status=200,
            body=json.dumps(self.interclient_response),
        )
        responses.add(
            responses.GET,
            self.saml_app_url,
            status=200,
            body=html,
        )
        result = self.client.get_saml_response(self.saml_app_url, self.auth_session)
        self.assertEqual(result['SAMLResponse'], 'PHhtbC8+')
        self.assertEqual(result['RelayState'], 'rs')
        self.assertEqual(result['TargetUrl'], 'https://signin.aliyun.com/saml')

    @responses.activate
    def test_get_saml_response_app_with_existing_query_string(self):
        html = """<html><body><form><input name="SAMLResponse" type="hidden" value="eA=="/></form></body></html>"""
        base_url = self.saml_app_url + '?foo=bar'
        responses.add(responses.POST, self.okta_org_url + '/oauth2/v1/token', status=200, body=json.dumps(self.interclient_response))
        responses.add(
            responses.GET,
            re.compile(re.escape(base_url) + r'.*'),
            status=200,
            body=html,
        )
        result = self.client.get_saml_response(base_url, self.auth_session)
        self.assertEqual(result['SAMLResponse'], 'eA==')

    @responses.activate
    def test_get_saml_response_missing_saml_response(self):
        responses.add(responses.POST, self.okta_org_url + '/oauth2/v1/token', status=200, body=json.dumps(self.interclient_response))
        responses.add(responses.GET, self.saml_app_url, status=200, body='<html></html>')
        with self.assertRaises(errors.GimmeAWSCredsError):
            self.client.get_saml_response(self.saml_app_url, self.auth_session)

    @responses.activate
    def test_get_saml_response_http_error(self):
        responses.add(responses.POST, self.okta_org_url + '/oauth2/v1/token', status=200, body=json.dumps(self.interclient_response))
        responses.add(responses.GET, self.saml_app_url, status=500)
        with self.assertRaises(Exception):
            self.client.get_saml_response(self.saml_app_url, self.auth_session)

    def test_enumerate_saml_roles_single(self):
        b64 = _b64_xml(ALIBABA_CLOUD_ASSERTION_XML)
        roles = AlibabaCloudClient.enumerate_saml_roles(b64)
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0], AlibabaCloudRoleSet(
            role_arn='acs:ram::111122223333:role/Admin',
            saml_provider_arn='acs:ram::111122223333:saml-provider/Okta',
            account_id='111122223333',
        ))

    def test_enumerate_saml_roles_multiple(self):
        b64 = _b64_xml(ALIBABA_CLOUD_ASSERTION_MULTI)
        roles = AlibabaCloudClient.enumerate_saml_roles(b64)
        self.assertEqual(len(roles), 2)
        self.assertEqual(roles[0].account_id, '111122223333')
        self.assertEqual(roles[1].account_id, '444455556666')

    def test_enumerate_saml_roles_malformed_pair(self):
        bad = """<?xml version="1.0" encoding="UTF-8"?>
<Assertion xmlns="urn:oasis:names:tc:SAML:2.0:assertion">
  <AttributeStatement>
    <Attribute Name="https://www.aliyun.com/SAML-Role/Attributes/Role">
      <AttributeValue>only-one-part</AttributeValue>
    </Attribute>
  </AttributeStatement>
</Assertion>"""
        b64 = _b64_xml(bad)
        with self.assertRaises(errors.GimmeAWSCredsError):
            AlibabaCloudClient.enumerate_saml_roles(b64)

    def _make_mock_sts_response(self):
        mock_creds = MagicMock()
        mock_creds.access_key_id = 'AKIA'
        mock_creds.access_key_secret = 'SECRET'
        mock_creds.security_token = 'TOKEN'
        mock_creds.expiration = '2026-01-01T00:00:00Z'
        mock_response = MagicMock()
        mock_response.body.credentials = mock_creds
        return mock_response

    @patch('gimme_aws_creds.alibaba_cloud.ALIBABA_CLOUD_SDK_AVAILABLE', True)
    @patch('gimme_aws_creds.alibaba_cloud._sts_client')
    def test_assume_role_with_saml(self, mock_sts_module):
        mock_client = MagicMock()
        mock_sts_module.Client.return_value = mock_client
        mock_client.assume_role_with_saml.return_value = self._make_mock_sts_response()

        c = AlibabaCloudClient(requests.Session(), 'https://x.okta.com', 'cid', verify_ssl_certs=True)
        out = c.assume_role_with_saml(
            'acs:ram::1:role/R',
            'acs:ram::1:saml-provider/P',
            'BASE64ASSERTION',
            duration=3600,
            region_id='cn-shanghai',
        )
        self.assertEqual(out['AccessKeyId'], 'AKIA')
        self.assertEqual(out['AccessKeySecret'], 'SECRET')
        self.assertEqual(out['SecurityToken'], 'TOKEN')
        self.assertEqual(out['Expiration'], '2026-01-01T00:00:00Z')
        mock_sts_module.Client.assert_called_once()
        config_arg = mock_sts_module.Client.call_args[0][0]
        self.assertEqual(config_arg.region_id, 'cn-shanghai')
        self.assertEqual(config_arg.endpoint, 'sts.cn-shanghai.aliyuncs.com')
        mock_client.assume_role_with_saml.assert_called_once()
        mock_client.assume_role_with_samlwith_options.assert_not_called()

    @patch('gimme_aws_creds.alibaba_cloud.ALIBABA_CLOUD_SDK_AVAILABLE', True)
    @patch('gimme_aws_creds.alibaba_cloud._sts_client')
    def test_assume_role_with_saml_ignore_ssl(self, mock_sts_module):
        mock_client = MagicMock()
        mock_sts_module.Client.return_value = mock_client
        mock_client.assume_role_with_samlwith_options.return_value = self._make_mock_sts_response()

        c = AlibabaCloudClient(requests.Session(), 'https://x.okta.com', 'cid', verify_ssl_certs=False)
        out = c.assume_role_with_saml(
            'acs:ram::1:role/R',
            'acs:ram::1:saml-provider/P',
            'BASE64ASSERTION',
        )
        self.assertEqual(out['AccessKeyId'], 'AKIA')
        mock_client.assume_role_with_samlwith_options.assert_called_once()
        runtime_arg = mock_client.assume_role_with_samlwith_options.call_args[0][1]
        self.assertTrue(runtime_arg.ignore_ssl)
        mock_client.assume_role_with_saml.assert_not_called()

    @patch('gimme_aws_creds.alibaba_cloud.ALIBABA_CLOUD_SDK_AVAILABLE', True)
    @patch('gimme_aws_creds.alibaba_cloud._sts_client')
    def test_assume_role_with_saml_clamps_duration(self, mock_sts_module):
        mock_client = MagicMock()
        mock_sts_module.Client.return_value = mock_client
        mock_client.assume_role_with_saml.return_value = self._make_mock_sts_response()

        c = AlibabaCloudClient(requests.Session(), 'https://x.okta.com', 'cid', verify_ssl_certs=True)
        c.assume_role_with_saml(
            'acs:ram::1:role/R',
            'acs:ram::1:saml-provider/P',
            'BASE64ASSERTION',
            duration=7200,
        )
        request_arg = mock_client.assume_role_with_saml.call_args[0][0]
        self.assertEqual(request_arg.duration_seconds, 3600)

    @patch('gimme_aws_creds.alibaba_cloud.ALIBABA_CLOUD_SDK_AVAILABLE', False)
    def test_assume_role_with_saml_requires_optional_sdk(self):
        c = AlibabaCloudClient(requests.Session(), 'https://x.okta.com', 'cid', verify_ssl_certs=False)
        with self.assertRaises(errors.GimmeAWSCredsError) as ctx:
            c.assume_role_with_saml(
                'acs:ram::1:role/R',
                'acs:ram::1:saml-provider/P',
                'BASE64ASSERTION',
            )
        self.assertIn('optional', ctx.exception.message.lower())


class TestEnumerateModule(unittest.TestCase):
    """Module-level enumerate matches class static method."""

    def test_module_enumerate_matches_class(self):
        b64 = _b64_xml(ALIBABA_CLOUD_ASSERTION_XML)
        self.assertEqual(
            enumerate_saml_roles(b64),
            AlibabaCloudClient.enumerate_saml_roles(b64),
        )


if __name__ == '__main__':
    unittest.main()
