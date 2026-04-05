"""
Copyright 2016-present Nike, Inc.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
"""
import base64
import re
import sys
import platform
import xml.etree.ElementTree as ET
from collections import namedtuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

try:
    from alibabacloud_sts20150401 import client as _sts_client
    from alibabacloud_sts20150401 import models as _sts_models
    from alibabacloud_tea_openapi import models as _open_api_models
    from alibabacloud_tea_util import models as _util_models
    ALIBABA_CLOUD_SDK_AVAILABLE = True
except ImportError:
    ALIBABA_CLOUD_SDK_AVAILABLE = False

from . import errors, version

ALIBABA_CLOUD_SAML_ROLE_ATTRIBUTE = 'https://www.aliyun.com/SAML-Role/Attributes/Role'

AlibabaCloudRoleSet = namedtuple('AlibabaCloudRoleSet', ['role_arn', 'saml_provider_arn', 'account_id'])

ALIBABA_CLOUD_SDK_INSTALL_HINT = (
    'Install optional Alibaba Cloud SDK packages, e.g. '
    'pip install "gimme-aws-creds[alicloud]"'
)


def _user_agent():
    return "gimme-aws-creds {};{};{}".format(version, sys.platform, platform.python_version())


def _request_headers_json():
    return {
        'User-Agent': _user_agent(),
        'Accept': 'application/json',
    }

def _account_id_from_role_arn(role_arn):
    m = re.match(r'acs:ram::(\d+):', role_arn)
    if not m:
        return ''
    return m.group(1)

class AlibabaCloudClient(object):
    """Alibaba Cloud RAM credentials via Okta Native-to-Web SSO (interclient token) and STS AssumeRoleWithSAML."""

    HTTP_TIMEOUT = 30

    def __init__(self, http_client, okta_org_url, client_id, verify_ssl_certs=True):
        """
        :param http_client: Shared ``requests.Session`` (e.g. OktaIdentityEngine._http_client).
        :param okta_org_url: Okta org base URL.
        :param client_id: OAuth client ID for token exchange.
        :param verify_ssl_certs: Whether to verify TLS certificates.
        """
        if not isinstance(http_client, requests.Session):
            raise errors.GimmeAWSCredsError('http_client must be a requests.Session', 2)
        self._http_client = http_client
        self._okta_org_url = okta_org_url.rstrip('/')
        self._client_id = client_id
        self._verify_ssl_certs = verify_ssl_certs
    
    def _interclient_token_exchange(self, app_id, access_token, id_token):
        response = self._http_client.post(
            self._okta_org_url + '/oauth2/v1/token',
            headers=_request_headers_json(),
            data={
                'actor_token': access_token,
                'actor_token_type': 'urn:ietf:params:oauth:token-type:access_token',
                'client_id': self._client_id,
                'audience': 'urn:okta:apps:{}'.format(app_id),
                'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
                'requested_token_type': 'urn:okta:params:oauth:token-type:interclient_token',
                'subject_token': id_token,
                'subject_token_type': 'urn:ietf:params:oauth:token-type:id_token',
            },
            verify=self._verify_ssl_certs,
            timeout=self.HTTP_TIMEOUT,
        )
        try:
            response_data = response.json()
        except ValueError as e:
            raise errors.GimmeAWSCredsError(
                'Invalid JSON response from token exchange endpoint: {}'.format(str(e)), 2)

        if response.status_code == 200:
            return response_data
        if response.status_code == 400:
            raise errors.GimmeAWSCredsError(
                'LOGIN ERROR: Interclient token exchange failed: {}'.format(
                    response_data.get('error_description', 'Unknown error')), 2)
        response.raise_for_status()
        return None

    @staticmethod
    def _saml_app_fetch_url(saml_app_url, interclient_token):
        sep = '&' if '?' in saml_app_url else '?'
        return '{}{}interclient_token={}'.format(saml_app_url, sep, quote(interclient_token, safe=''))

    def get_saml_response(self, saml_sso_url, saml_app_url, auth_session):
        """Exchange for an interclient token and GET the Alibaba Cloud SAML app page; parse SAMLResponse form fields."""
        app_id = saml_app_url.split('/')[-2]
        token_payload = self._interclient_token_exchange(
            app_id, auth_session['access_token'], auth_session['id_token'])
        interclient_token = token_payload['access_token']

        fetch_url = self._saml_app_fetch_url(saml_sso_url, interclient_token)
        response = self._http_client.get(
            fetch_url,
            headers=_request_headers_json(),
            verify=self._verify_ssl_certs,
            timeout=self.HTTP_TIMEOUT,
        )

        if response.status_code != 200:
            response.raise_for_status()

        saml_response = None
        relay_state = None
        form_action = None

        saml_soup = BeautifulSoup(response.text, 'html.parser')
        if saml_soup.find('form') is not None:
            form_action = saml_soup.find('form').get('action')
        for input_tag in saml_soup.find_all('input'):
            if input_tag.get('name') == 'SAMLResponse':
                saml_response = input_tag.get('value')
            elif input_tag.get('name') == 'RelayState':
                relay_state = input_tag.get('value')

        if saml_response is None:
            saml_error = 'Did not receive SAML Response after successful authentication [{}]'.format(saml_app_url)
            if saml_soup.find(class_='error-content') is not None:
                saml_error += '\n' + saml_soup.find(class_='error-content').get_text()
            raise errors.GimmeAWSCredsError(saml_error, 2)

        return {'SAMLResponse': saml_response, 'RelayState': relay_state, 'TargetUrl': form_action}

    @staticmethod
    def enumerate_saml_roles(assertion_b64):
        """Parse Alibaba Cloud role ARNs from a SAML assertion (base64). Role attribute values are ``role_arn,provider_arn``."""
        return AlibabaCloudClient._enumerate_saml_roles_impl(assertion_b64)

    @staticmethod
    def _enumerate_saml_roles_impl(assertion_b64):
        root = ET.fromstring(base64.b64decode(assertion_b64))
        roles = []
        for attr in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
            if attr.get('Name') != ALIBABA_CLOUD_SAML_ROLE_ATTRIBUTE:
                continue
            for val in attr.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
                text = (val.text or '').strip()
                if not text:
                    continue
                parts = [p.strip() for p in text.split(',')]
                if len(parts) != 2:
                    raise errors.GimmeAWSCredsError(
                        'Invalid Alibaba Cloud role pair (expected role_arn,saml_provider_arn): {}'.format(text), 2)
                role_arn, saml_provider_arn = parts[0], parts[1]
                roles.append(AlibabaCloudRoleSet(
                    role_arn=role_arn,
                    saml_provider_arn=saml_provider_arn,
                    account_id=_account_id_from_role_arn(role_arn),
                ))
        return roles

    def assume_role_with_saml(self, role_arn, saml_provider_arn, saml_assertion, duration=3600, region_id='cn-hangzhou'):
        """
        Call Alibaba Cloud STS AssumeRoleWithSAML using an anonymous regional client.

        :param saml_assertion: Raw SAML assertion XML, base64-encoded (same as POSTed SAMLResponse value).
        :param duration: Requested session duration in seconds. Alibaba Cloud caps this at 3600; larger values are silently clamped.
        """
        if not ALIBABA_CLOUD_SDK_AVAILABLE:
            raise errors.GimmeAWSCredsError(
                'Alibaba Cloud STS requires optional SDK packages. {}'.format(ALIBABA_CLOUD_SDK_INSTALL_HINT), 2)

        config = _open_api_models.Config(
            access_key_id='',
            access_key_secret='',
            region_id=region_id,
            endpoint='sts.{}.aliyuncs.com'.format(region_id),
        )
        client = _sts_client.Client(config)
        try:
            request = _sts_models.AssumeRoleWithSAMLRequest(
                role_arn=role_arn,
                samlprovider_arn=saml_provider_arn,
                samlassertion=saml_assertion,
                duration_seconds=duration,
            )
        except Exception as e:
            print(type(e))
            print(e)
            print(e.name)


        if self._verify_ssl_certs is False:
            runtime = _util_models.RuntimeOptions(ignore_ssl=True)
            response = client.assume_role_with_samlwith_options(request, runtime)
        else:
            response = client.assume_role_with_saml(request)

        creds = response.body.credentials
        return {
            'AccessKeyId': creds.access_key_id,
            'AccessKeySecret': creds.access_key_secret,
            'SecurityToken': creds.security_token,
            'Expiration': creds.expiration,
        }


def enumerate_saml_roles(assertion_b64):
    """Parse Alibaba Cloud ``role_arn,saml_provider_arn`` pairs from a base64-encoded SAML assertion."""
    return AlibabaCloudClient._enumerate_saml_roles_impl(assertion_b64)
