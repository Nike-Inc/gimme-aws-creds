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
import getpass
import re
import sys
import time
import uuid
from codecs import decode
from urllib.parse import parse_qs
from urllib.parse import urlparse

import keyring
import requests
from bs4 import BeautifulSoup
from keyring.backends.fail import Keyring as FailKeyring
from keyring.errors import PasswordDeleteError
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from . import version


class OktaClient(object):
    """
       The Okta Client Class performes the necessary API
       calls to Okta to get temporary AWS credentials. An
       Okta API key and URL must be provided.
    """

    KEYRING_SERVICE = 'gimme-aws-creds'
    KEYRING_ENABLED = not isinstance(keyring.get_keyring(), FailKeyring)

    def __init__(self, okta_org_url, verify_ssl_certs=True, device_token=None):
        """
        :param okta_org_url: Base URL string for Okta IDP.
        :param verify_ssl_certs: Enable/disable SSL verification
        """
        self._okta_org_url = okta_org_url
        self._verify_ssl_certs = verify_ssl_certs

        if verify_ssl_certs is False:
            requests.packages.urllib3.disable_warnings()

        self._username = None
        self._preferred_mfa_type = None
        self._mfa_code = None
        self._remember_device = None

        self._use_oauth_access_token = False
        self._use_oauth_id_token = False
        self._oauth_access_token = None
        self._oauth_id_token = None

        jar = requests.cookies.RequestsCookieJar()

        if device_token is not None:
            match = re.search('^https://(.*)', okta_org_url)
            jar.set('DT', device_token, domain=match.group(1), path='/')

        # Allow up to 5 retries on requests to Okta in case we have network issues
        self._http_client = requests.Session()
        self._http_client.cookies = jar

        retries = Retry(total=5, backoff_factor=1,
                        method_whitelist=['GET', 'POST'])
        self._http_client.mount('https://', HTTPAdapter(max_retries=retries))

    def set_username(self, username):
        self._username = username

    def set_preferred_mfa_type(self, preferred_mfa_type):
        self._preferred_mfa_type = preferred_mfa_type

    def set_mfa_code(self, mfa_code):
        self._mfa_code = mfa_code

    def set_remember_device(self, remember_device):
        self._remember_device = remember_device

    def use_oauth_access_token(self, val=True):
        self._use_oauth_access_token = val

    def use_oauth_id_token(self, val=True):
        self._use_oauth_id_token = val

    def stepup_auth(self, embed_link, state_token=None):
        """ Login to Okta using the Step-up authentication flow"""
        flow_state = self._get_initial_flow_state(embed_link, state_token)

        while flow_state.get('apiResponse').get('status') != 'SUCCESS':
            flow_state = self._next_login_step(
                flow_state.get('stateToken'), flow_state.get('apiResponse'))

        return flow_state['apiResponse']

    def stepup_auth_saml(self, embed_link, state_token=None):
        """ Login to a SAML-protected service using the Step-up authentication flow"""
        api_response = self.stepup_auth(embed_link, state_token)

        # if a session token is in the API response, we can use that to authenticate
        if 'sessionToken' in api_response:
            saml_response = self.get_saml_response(
                embed_link + '?sessionToken=' + api_response['sessionToken'])
        else:
            saml_response = self.get_saml_response(
                api_response['_links']['next']['href'])

        login_result = self._http_client.post(
            saml_response['TargetUrl'],
            data=saml_response,
            verify=self._verify_ssl_certs
        )
        return login_result.text

    def auth(self):
        """ Login to Okta using the authentication API"""
        flow_state = self._login_username_password(None, self._okta_org_url + '/api/v1/authn')

        while flow_state.get('apiResponse').get('status') != 'SUCCESS':
            flow_state = self._next_login_step(
                flow_state.get('stateToken'), flow_state.get('apiResponse'))

        return flow_state['apiResponse']

    def auth_session(self, **kwargs):
        """ Authenticate the user and return the Okta Session ID and username"""
        login_response = self.auth()

        session_url = self._okta_org_url + '/login/sessionCookieRedirect'

        if 'redirect_uri' not in kwargs:
            redirect_uri = 'http://localhost:8080/login'
        else:
            redirect_uri = kwargs['redirect_uri']

        params = {
            'token': login_response['sessionToken'],
            'redirectUrl': redirect_uri
        }

        response = self._http_client.get(
            session_url,
            params=params,
            headers=self._get_headers(),
            verify=self._verify_ssl_certs,
            allow_redirects=False
        )
        return {"username": login_response['_embedded']['user']['profile']['login'], "session": response.cookies['sid'], "device_token": self._http_client.cookies['DT']}

    def auth_oauth(self, client_id, **kwargs):
        """ Login to Okta and retrieve access token, ID token or both """
        login_response = self.auth()

        if 'access_token' not in kwargs:
            access_token = True
        else:
            access_token = kwargs['access_token']

        if 'id_token' not in kwargs:
            id_token = False
        else:
            id_token = kwargs['id_token']

        if 'scopes' not in kwargs:
            scopes = ['openid']
        else:
            scopes = kwargs['scopes']

        response_types = []
        if id_token is True:
            response_types.append('id_token')
        if access_token is True:
            response_types.append('token')

        if 'authorization_server' not in kwargs:
            oauth_url = self._okta_org_url + '/oauth2/v1/authorize'
        else:
            oauth_url = self._okta_org_url + '/oauth2/' + kwargs['authorization_server'] + '/v1/authorize'

        if 'redirect_uri' not in kwargs:
            redirect_uri = 'http://localhost:8080/login'
        else:
            redirect_uri = kwargs['redirect_uri']

        if 'nonce' not in kwargs:
            nonce = uuid.uuid4().hex
        else:
            nonce = kwargs['nonce']

        if 'state' not in kwargs:
            state = 'auth_oauth'
        else:
            state = kwargs['state']

        params = {
            'sessionToken': login_response['sessionToken'],
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'nonce': nonce,
            'state': state,
            'response_type': ' '.join(response_types),
            'scope': ' '.join(scopes)
        }

        response = self._http_client.get(
            oauth_url,
            params=params,
            headers=self._get_headers(),
            verify=self._verify_ssl_certs,
            allow_redirects=False
        )

        url_parse_results = urlparse(response.headers['Location'])
        query_result = parse_qs(url_parse_results.fragment)

        tokens = {}
        if 'access_token' in query_result:
            tokens['access_token'] = query_result['access_token'][0]
            self._oauth_access_token = query_result['access_token'][0]
        if 'id_token' in query_result:
            tokens['id_token'] = query_result['id_token'][0]
            self._oauth_id_token = query_result['id_token'][0]

        return tokens

    @staticmethod
    def _get_headers():
        """sets the default headers"""
        headers = {
            'User-Agent': "gimme-aws-creds {}".format(version),
            'Accept': 'application/json',
            'Content-Type': 'application/json'}
        return headers

    def _get_initial_flow_state(self, embed_link, state_token=None):
        """ Starts the authentication flow with Okta"""
        if state_token is None:
            response = self._http_client.get(
                embed_link, allow_redirects=False)
            url_parse_results = urlparse(response.headers['Location'])
            state_token = parse_qs(url_parse_results.query)['stateToken'][0]

        response = self._http_client.post(
            self._okta_org_url + '/api/v1/authn',
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        return {'stateToken': state_token, 'apiResponse': response.json()}

    def _next_login_step(self, state_token, login_data):
        """ decide what the next step in the login process is"""
        if 'errorCode' in login_data:
            print("LOGIN ERROR: {} | Error Code: {}".format(login_data['errorSummary'], login_data['errorCode']), file=sys.stderr)
            exit(2)

        status = login_data['status']

        if status == 'UNAUTHENTICATED':
            return self._login_username_password(state_token, login_data['_links']['next']['href'])
        elif status == 'LOCKED_OUT':
            print("Your Okta access has been locked out due to failed login attempts.", file=sys.stderr)
            exit(2)
        elif status == 'MFA_ENROLL':
            print("You must enroll in MFA before using this tool.", file=sys.stderr)
            exit(2)
        elif status == 'MFA_REQUIRED':
            return self._login_multi_factor(state_token, login_data)
        elif status == 'MFA_CHALLENGE':
            if 'factorResult' in login_data and login_data['factorResult'] == 'WAITING':
                return self._check_push_result(state_token, login_data)
            else:
                return self._login_input_mfa_challenge(state_token, login_data['_links']['next']['href'])
        else:
            raise RuntimeError('Unknown login status: ' + status)

    def _login_username_password(self, state_token, url):
        """ login to Okta with a username and password"""
        creds = self._get_username_password_creds()

        login_json = {
            'username': creds['username'],
            'password': creds['password']
        }

        # If this isn't a Step-up auth flow, we won't have a stateToken
        if state_token is not None:
            login_json['stateToken'] = state_token

        response = self._http_client.post(
            url,
            json=login_json,
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        response_data = response.json()
        if 'errorCode' in response_data:
            print("LOGIN ERROR: {} | Error Code: {}".format(response_data['errorSummary'], response_data['errorCode']), file=sys.stderr)

            if self.KEYRING_ENABLED:
                try:
                    keyring.delete_password(self.KEYRING_SERVICE, creds['username'])
                except PasswordDeleteError:
                    pass

            exit(2)

        func_result = {'apiResponse': response_data}
        if 'stateToken' in response_data:
            func_result['stateToken'] = response_data['stateToken']

        return func_result

    def _login_send_sms(self, state_token, factor):
        """ Send SMS message for second factor authentication"""
        response = self._http_client.post(
            factor['_links']['verify']['href'],
            params={'rememberDevice': self._remember_device},
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        print("A verification code has been sent to " + factor['profile']['phoneNumber'], file=sys.stderr)
        response_data = response.json()

        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    def _login_send_call(self, state_token, factor):
        """ Send Voice call for second factor authentication"""
        response = self._http_client.post(
            factor['_links']['verify']['href'],
            params={'rememberDevice': self._remember_device},
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        print("You should soon receive a phone call at " + factor['profile']['phoneNumber'], file=sys.stderr)
        response_data = response.json()

        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    def _login_send_push(self, state_token, factor):
        """ Send 'push' for the Okta Verify mobile app """
        response = self._http_client.post(
            factor['_links']['verify']['href'],
            params={'rememberDevice': self._remember_device},
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        print("Okta Verify push sent...", file=sys.stderr)
        response_data = response.json()

        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    def _login_multi_factor(self, state_token, login_data):
        """ handle multi-factor authentication with Okta"""
        factor = self._choose_factor(login_data['_embedded']['factors'])
        if factor['factorType'] == 'sms':
            return self._login_send_sms(state_token, factor)
        elif factor['factorType'] == 'call':
            return self._login_send_call(state_token, factor)
        elif factor['factorType'] == 'token:software:totp':
            return self._login_input_mfa_challenge(state_token, factor['_links']['verify']['href'])
        elif factor['factorType'] == 'token':
            return self._login_input_mfa_challenge(state_token, factor['_links']['verify']['href'])
        elif factor['factorType'] == 'push':
            return self._login_send_push(state_token, factor)

    def _login_input_mfa_challenge(self, state_token, next_url):
        """ Submit verification code for SMS or TOTP authentication methods"""
        pass_code = self._mfa_code;
        if pass_code is None:
            print("Enter verification code: ", end='', file=sys.stderr)
            pass_code = input()
        response = self._http_client.post(
            next_url,
            params={'rememberDevice': self._remember_device},
            json={'stateToken': state_token, 'passCode': pass_code},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        response_data = response.json()
        if 'status' in response_data and response_data['status'] == 'SUCCESS':
            if 'stateToken' in response_data:
                return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
            if 'sessionToken' in response_data:
                return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}
        else:
            return {'stateToken': None, 'sessionToken': None, 'apiResponse': response_data}

    def _check_push_result(self, state_token, login_data):
        """ Check Okta API to see if the push request has been responded to"""
        time.sleep(1)
        response = self._http_client.post(
            login_data['_links']['next']['href'],
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        response_data = response.json()
        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    def get_saml_response(self, url):
        """ return the base64 SAML value object from the SAML Response"""
        response = self._http_client.get(url, verify=self._verify_ssl_certs)

        saml_response = None
        relay_state = None
        form_action = None

        saml_soup = BeautifulSoup(response.text, "html.parser")
        if saml_soup.find('form') is not None:
            form_action = saml_soup.find('form').get('action')
        for inputtag in saml_soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                saml_response = inputtag.get('value')
            elif inputtag.get('name') == 'RelayState':
                relay_state = inputtag.get('value')

        if saml_response is None:
            # We didn't get a SAML response.  Were we redirected to an MFA login page?
            if hasattr(saml_soup.title, 'string') and re.match(".* - Extra Verification$", saml_soup.title.string):
                # extract the stateToken from the Javascript code in the page and step up to MFA
                state_token = decode(re.search(r"var stateToken = '(.*)';", response.text).group(1), "unicode-escape")
                api_response = self.stepup_auth(url, state_token)
                saml_response = self.get_saml_response(url + '?sessionToken=' + api_response['sessionToken'])

                return saml_response

            raise RuntimeError(
                'Did not receive SAML Response after successful authentication [' + url + ']')

        return {'SAMLResponse': saml_response, 'RelayState': relay_state, 'TargetUrl': form_action}

    def get(self, url, **kwargs):
        """ Retrieve resource that is protected by Okta """
        if self._use_oauth_access_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        if self._use_oauth_id_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)
        return self._http_client.get(url, **kwargs)

    def post(self, url, **kwargs):
        """ Create resource that is protected by Okta """
        if self._use_oauth_access_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        if self._use_oauth_id_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)
        return self._http_client.post(url, **kwargs)

    def put(self, url, **kwargs):
        """ Modify resource that is protected by Okta """
        if self._use_oauth_access_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        if self._use_oauth_id_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)
        return self._http_client.put(url, **kwargs)

    def delete(self, url, **kwargs):
        """ Delete resource that is protected by Okta """
        if self._use_oauth_access_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        if self._use_oauth_id_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)
        return self._http_client.delete(url, **kwargs)

    def _choose_factor(self, factors):
        """ gets a list of available authentication factors and
        asks the user to select the factor they want to use """

        print("Multi-factor Authentication required.", file=sys.stderr)

        # filter the factor list down to just the types specified in preferred_mfa_type
        if self._preferred_mfa_type is not None:
            factors = list(filter(lambda item: item['factorType'] == self._preferred_mfa_type, factors))

        if len(factors) == 1:
            factor_name = self._build_factor_name(factors[0])
            print(factor_name, 'selected', file=sys.stderr)
            selection = 0
        else:
            print("Pick a factor:", file=sys.stderr)
            # print out the factors and let the user select
            for i, factor in enumerate(factors):
                factor_name = self._build_factor_name(factor)
                if factor_name is not "":
                    print('[', i, ']', factor_name, file=sys.stderr)
            print("Selection: ", end='', file=sys.stderr)
            selection = input()

        # make sure the choice is valid
        if int(selection) > len(factors):
            print("You made an invalid selection", file=sys.stderr)
            exit(1)

        return factors[int(selection)]

    @staticmethod
    def _build_factor_name(factor):
        """ Build the display name for a MFA factor based on the factor type"""
        if factor['factorType'] == 'push':
            return "Okta Verify App: " + factor['profile']['deviceType'] + ": " + factor['profile']['name']
        elif factor['factorType'] == 'sms':
            return factor['factorType'] + ": " + factor['profile']['phoneNumber']
        elif factor['factorType'] == 'call':
            return factor['factorType'] + ": " + factor['profile']['phoneNumber']
        elif factor['factorType'] == 'token:software:totp':
            return factor['factorType'] + "( " + factor['provider'] + " ) : " + factor['profile']['credentialId']
        elif factor['factorType'] == 'token':
            return factor['factorType'] + ": " + factor['profile']['credentialId']
        else:
            return ("Unknown MFA type: " + factor['factorType'])

    def _get_username_password_creds(self):
        """Get's creds for Okta login from the user."""

        # Check to see if the username arg has been set, if so use that
        if self._username is not None:
            username = self._username
        # Otherwise just ask the user
        else:
            print("Username: ", end='', file=sys.stderr)
            username = input()
            self._username = username

        # noinspection PyBroadException
        password = None
        if self.KEYRING_ENABLED:
            try:
                # If the OS supports a keyring, offer to save the password
                password = keyring.get_password(self.KEYRING_SERVICE, username)
                print("Using password from keyring for {}".format(username), file=sys.stderr)
            except RuntimeError:
                print("Unable to get password from keyring.", file=sys.stderr)
        if not password:
            # Set prompt to include the user name, since username could be set
            # via OKTA_USERNAME env and user might not remember.
            for x in range(0, 5):
                passwd_prompt = "Password for {}: ".format(username)
                password = getpass.getpass(prompt=passwd_prompt)
                if len(password) > 0:
                    break

            if self.KEYRING_ENABLED:
                # If the OS supports a keyring, offer to save the password
                print("Do you want to save this password in the keyring? (y/n) ", end='', file=sys.stderr)
                if input() == 'y':
                    try:
                        keyring.set_password(self.KEYRING_SERVICE, username, password)
                        print("Password for {} saved in keyring.".format(username), file=sys.stderr)
                    except RuntimeError as err:
                        print("Failed to save password in keyring: ", err, file=sys.stderr)

        if not password:
            print('Password was not provided. Exiting.', file=sys.stderr)
            exit(1)

        return {'username': username, 'password': password}
