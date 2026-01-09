"""
Copyright 2016-present Nike, Inc.
Licensed under the Apache License, Version 2.0 (the "License");
You may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and* limitations under the License.*
"""
import sys
import platform
import time
import webbrowser
import urllib3
import jwt
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from . import errors, version

class OktaIdentityEngine(object):
    """
       The Okta Client Class performs the necessary API
       calls to an Okta Identity Engine domain to get temporary AWS credentials.
    """

    HTTP_TIMEOUT = 30  # Timeout in seconds for HTTP requests
    DEVICE_FLOW_TIMEOUT = 120  # Timeout in seconds for device authorization flow (60 iterations * 2 seconds)

    def __init__(self, gac_ui, okta_org_url, client_id, verify_ssl_certs=True, device_token=None, device_flow_timeout=None):
        """
        :type gac_ui: ui.UserInterface
        :param okta_org_url: Base URL string for Okta IDP.
        :param client_id: Client ID that will be used for user auth
        :param verify_ssl_certs: Enable/disable SSL verification
        """
        self.ui = gac_ui
        self._okta_org_url = okta_org_url
        self._client_id = client_id
        self._verify_ssl_certs = verify_ssl_certs
        
        self._use_oauth_access_token = False
        self._use_oauth_id_token = False
        self._oauth_access_token = None
        self._oauth_id_token = None
        self._device_flow_timeout = device_flow_timeout if device_flow_timeout is not None else self.DEVICE_FLOW_TIMEOUT

        if verify_ssl_certs is False:
            urllib3.disable_warnings()

        self._jar = requests.cookies.RequestsCookieJar()

        # Allow up to 5 retries on requests to Okta in case we have network issues
        self._http_client = requests.Session()
        self._http_client.cookies = self._jar

        retries = Retry(total=5, backoff_factor=1,
                        allowed_methods=['GET', 'POST'])
        self._http_client.mount('https://', HTTPAdapter(max_retries=retries))
    
    def use_oauth_access_token(self, val=True):
        self._use_oauth_access_token = val

    def use_oauth_id_token(self, val=True):
        self._use_oauth_id_token = val

    def auth_session(self, **kwargs):
        """ Authenticate the user and return the Okta Identity and access token"""
        login_response = self._start_device_flow()
        
        # Safe access to nested response data
        if 'apiResponse' not in login_response or 'verification_uri_complete' not in login_response['apiResponse']:
            raise errors.GimmeAWSCredsError("Invalid response from device authorization flow", 2)
        
        if 'open_browser' not in kwargs:
            open_browser = False
        else:
            open_browser = kwargs['open_browser']

        if open_browser:
            self.ui.info("The system web browser will open the following URL to begin Okta device authorization:")
            webbrowser.open(login_response['apiResponse']['verification_uri_complete'])
        else:
            self.ui.info("Open the following URL to begin Okta device authorization:")
        self.ui.info("")
        self.ui.info(login_response['apiResponse']['verification_uri_complete'])
        self.ui.info("")

        if 'device_code' not in login_response['apiResponse']:
            raise errors.GimmeAWSCredsError("Device code missing from authorization response", 2)
        
        token_response = self._get_user_tokens(login_response['apiResponse']['device_code'])
        
        # Calculate max iterations based on timeout (default 120 seconds / 2 second intervals = 60 iterations)
        max_iterations = self._device_flow_timeout // 2
        count = 0
        while token_response is None and count < max_iterations:
            time.sleep(2)
            token_response = self._get_user_tokens(login_response['apiResponse']['device_code'])
            count += 1
        
        if count >= max_iterations:
            raise errors.GimmeAWSCredsError(
                "Timeout waiting for device authorization ({} seconds)".format(self._device_flow_timeout), 2)
        
        # Safe access to token response fields
        if 'access_token' not in token_response:
            raise errors.GimmeAWSCredsError("Access token missing from token response", 2)
            
        at_data = jwt.decode(token_response['access_token'], options={"verify_signature": False})
        
        return {
            'username': at_data['sub'],
            'access_token': token_response['access_token'],
            'id_token': token_response.get('id_token', ''),
            'scope': token_response.get('scope', '')
        }

    def _start_device_flow(self):
        response = self._http_client.post(
            self._okta_org_url + '/oauth2/v1/device/authorize',
            headers=self._get_headers(),
            data={'scope':'openid okta.apps.sso', 'client_id': self._client_id },
            verify=self._verify_ssl_certs,
            timeout=self.HTTP_TIMEOUT
        )

        # Safe JSON parsing with error handling
        try:
            response_data = response.json()
        except ValueError as e:
            raise errors.GimmeAWSCredsError(
                "Invalid JSON response from device authorization endpoint: {}".format(str(e)), 2)

        if response.status_code == 200:
            func_result = {'apiResponse': response_data}
            return func_result
        else:
            response.raise_for_status()
    
    def _get_user_tokens(self, device_code):
        response = self._http_client.post(
            self._okta_org_url + '/oauth2/v1/token',
            headers=self._get_headers(),
            data={'client_id':self._client_id, 'device_code': device_code, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'},
            verify=self._verify_ssl_certs,
            timeout=self.HTTP_TIMEOUT
        )

        # Safe JSON parsing with error handling
        try:
            response_data = response.json()
        except ValueError as e:
            raise errors.GimmeAWSCredsError(
                "Invalid JSON response from token endpoint: {}".format(str(e)), 2)

        if response.status_code == 200:
            self._oauth_access_token = response_data.get('access_token')
            self._oauth_id_token = response_data.get('id_token')
            return response_data
        elif response.status_code == 400 and response_data.get('error') == 'authorization_pending':
            return None
        else:
            response.raise_for_status()
            return None
    
    def _web_sso_token_exchange(self, app_id, access_token, id_token):
        response = self._http_client.post(
            self._okta_org_url + '/oauth2/v1/token',
            headers=self._get_headers(),
            data = {  
                'actor_token': access_token,
                'actor_token_type': 'urn:ietf:params:oauth:token-type:access_token',
                'client_id': self._client_id, 
                'audience': "urn:okta:apps:{}".format(app_id), 
                'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
                'requested_token_type': 'urn:okta:oauth:token-type:web_sso_token',
                'subject_token': id_token,
                'subject_token_type': 'urn:ietf:params:oauth:token-type:id_token'
            },
            verify=self._verify_ssl_certs,
            timeout=self.HTTP_TIMEOUT
        )

        # Safe JSON parsing with error handling
        try:
            response_data = response.json()
        except ValueError as e:
            raise errors.GimmeAWSCredsError(
                "Invalid JSON response from token exchange endpoint: {}".format(str(e)), 2)

        if response.status_code == 200:
            return response_data
        else:
            response.raise_for_status()

    def get_saml_response(self, url, auth_session):

        # extract the ID from the app link
        app_id = url.split('/')[-2]

        web_sso_token = self._web_sso_token_exchange(app_id, auth_session['access_token'], auth_session['id_token'])

        # Get the SAML response with the Web SSO token
        response = self._http_client.get(
            '{}/login/token/sso?token={}'.format(self._okta_org_url, web_sso_token['access_token']),
            headers=self._get_headers(),
            timeout=self.HTTP_TIMEOUT
        )

        if response.status_code == 200:
            saml_response = None
            relay_state = None
            form_action = None

            saml_soup = BeautifulSoup(response.text, "html.parser")
            if saml_soup.find('form') is not None:
                form_action = saml_soup.find('form').get('action')
            for input_tag in saml_soup.find_all('input'):
                if input_tag.get('name') == 'SAMLResponse':
                    saml_response = input_tag.get('value')
                elif input_tag.get('name') == 'RelayState':
                    relay_state = input_tag.get('value')
            
            if saml_response is None:
                saml_error = 'Did not receive SAML Response after successful authentication [' + url + ']'
                if saml_soup.find(class_='error-content') is not None:
                    saml_error += '\n' + saml_soup.find(class_='error-content').get_text()

                raise RuntimeError(saml_error)

        else:
            response.raise_for_status()
        
        return {'SAMLResponse': saml_response, 'RelayState': relay_state, 'TargetUrl': form_action}

    @staticmethod
    def _get_headers():
        """sets the default headers"""
        headers = {
            'User-Agent': "gimme-aws-creds {};{};{}".format(version, sys.platform, platform.python_version()),
            'Accept': 'application/json'
        }
        return headers
    
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