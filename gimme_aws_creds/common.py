"""
Copyright 2018-present SYNETIS.
Licensed under the Apache License, Version 2.0 (the "License");
You may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and* limitations under the License.*
"""
import base64
import platform
import sys
import xml.etree.ElementTree as ET
from collections import namedtuple

from bs4 import BeautifulSoup

RoleSet = namedtuple('RoleSet', 'idp, role, friendly_account_name, friendly_role_name')


class FakeAssertion:
    """Stub assertion returned when a real FIDO/WebAuthn device is unavailable."""
    def __init__(self):
        self.signature = b'fake'
        self.auth_data = b'fake'


def user_agent():
    """Canonical User-Agent string shared across all HTTP callers."""
    from gimme_aws_creds import version
    return "gimme-aws-creds {};{};{}".format(version, sys.platform, platform.python_version())


def request_headers_json():
    """Standard JSON Accept + User-Agent headers."""
    return {
        'User-Agent': user_agent(),
        'Accept': 'application/json',
    }


def parse_saml_form(html_text):
    """Extract SAMLResponse, RelayState, and form action from an HTML SAML form."""
    soup = BeautifulSoup(html_text, 'html.parser')
    form_action = None
    if soup.find('form') is not None:
        form_action = soup.find('form').get('action')
    fields = {}
    for input_tag in soup.find_all('input'):
        name = input_tag.get('name')
        if name in ('SAMLResponse', 'RelayState'):
            fields[name] = input_tag.get('value')
    return fields.get('SAMLResponse'), fields.get('RelayState'), form_action


def parse_saml_role_attributes(assertion_b64, attribute_name):
    """Yield raw text values from the named SAML attribute in a base64 assertion."""
    root = ET.fromstring(base64.b64decode(assertion_b64))
    for attr in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
        if attr.get('Name') != attribute_name:
            continue
        for val in attr.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
            text = (val.text or '').strip()
            if text:
                yield text


def create_http_session(verify_ssl=True, allowed_methods=None, debug=False):
    """Create a requests.Session with retry logic and optional SSL/debug configuration."""
    import urllib3
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    if not verify_ssl:
        urllib3.disable_warnings()

    session = requests.Session()
    methods = allowed_methods or ['GET', 'POST']
    retries = Retry(total=5, backoff_factor=1, allowed_methods=methods)
    session.mount('https://', HTTPAdapter(max_retries=retries))

    if debug:
        from .debug_formatter import create_debug_response_hook
        session.hooks['response'].append(create_debug_response_hook())

    return session


class OktaHttpMixin:
    """Shared OAuth-aware HTTP methods for Okta client classes.

    Expects the host class to define:
      - _use_oauth_access_token (bool)
      - _use_oauth_id_token (bool)
      - _oauth_access_token (str | None)
      - _oauth_id_token (str | None)
      - _http_client (requests.Session)
      - HTTP_TIMEOUT (int)
    """

    def check_kwargs(self, kwargs):
        if self._use_oauth_access_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        if self._use_oauth_id_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_id_token)

        return kwargs

    def get(self, url, **kwargs):
        """ Retrieve resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        if 'timeout' not in parameters:
            parameters['timeout'] = self.HTTP_TIMEOUT
        return self._http_client.get(url, **parameters)

    def post(self, url, **kwargs):
        """ Create resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        if 'timeout' not in parameters:
            parameters['timeout'] = self.HTTP_TIMEOUT
        return self._http_client.post(url, **parameters)

    def put(self, url, **kwargs):
        """ Modify resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        if 'timeout' not in parameters:
            parameters['timeout'] = self.HTTP_TIMEOUT
        return self._http_client.put(url, **parameters)

    def delete(self, url, **kwargs):
        """ Delete resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        if 'timeout' not in parameters:
            parameters['timeout'] = self.HTTP_TIMEOUT
        return self._http_client.delete(url, **parameters)


def okta_token_exchange(http_client, okta_org_url, client_id, app_id, access_token, id_token,
                        requested_token_type, verify_ssl=True, timeout=30):
    """Perform an Okta OAuth2 token exchange (used by both OIE Web SSO and AliCloud interclient flows)."""
    from . import errors
    response = http_client.post(
        okta_org_url.rstrip('/') + '/oauth2/v1/token',
        headers=request_headers_json(),
        data={
            'actor_token': access_token,
            'actor_token_type': 'urn:ietf:params:oauth:token-type:access_token',
            'client_id': client_id,
            'audience': 'urn:okta:apps:{}'.format(app_id),
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'requested_token_type': requested_token_type,
            'subject_token': id_token,
            'subject_token_type': 'urn:ietf:params:oauth:token-type:id_token',
        },
        verify=verify_ssl,
        timeout=timeout,
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
            'LOGIN ERROR: Token exchange failed: {}'.format(
                response_data.get('error_description', 'Unknown error')), 2)
    response.raise_for_status()
    return None
