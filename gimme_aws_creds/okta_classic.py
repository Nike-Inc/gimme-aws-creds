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
import base64
import copy
import getpass
import re
import socket
import time
import uuid
import webbrowser
from codecs import decode
from multiprocessing import Process
from urllib.parse import parse_qs
from urllib.parse import urlparse, quote

import keyring
import requests
from bs4 import BeautifulSoup
from fido2.utils import websafe_decode
from keyring.backends.fail import Keyring as FailKeyring
from keyring.errors import PasswordDeleteError
from requests.adapters import HTTPAdapter, Retry

from gimme_aws_creds.u2f import FactorU2F
from gimme_aws_creds.webauthn import WebAuthnClient, FakeAssertion
from . import errors, ui, version, duo
from .errors import GimmeAWSCredsMFAEnrollStatus
from .registered_authenticators import RegisteredAuthenticators


class OktaClassicClient(object):
    """
       The Okta Client Class performs the necessary API
       calls to an Okta Classic domain to get temporary AWS credentials.
    """

    KEYRING_SERVICE = 'gimme-aws-creds'
    KEYRING_ENABLED = not isinstance(keyring.get_keyring(), FailKeyring)

    def __init__(self, gac_ui, okta_org_url, verify_ssl_certs=True, device_token=None):
        """
        :type gac_ui: ui.UserInterface
        :param okta_org_url: Base URL string for Okta IDP.
        :param verify_ssl_certs: Enable/disable SSL verification
        :param device_token: Device Token value for Okta device ID
        """
        self.ui = gac_ui
        self._okta_org_url = okta_org_url
        self._verify_ssl_certs = verify_ssl_certs

        if verify_ssl_certs is False:
            requests.packages.urllib3.disable_warnings()

        self._username = None
        self._password = None
        self._preferred_mfa_type = None
        self._mfa_code = None
        self._remember_device = None

        self._use_oauth_access_token = False
        self._use_oauth_id_token = False
        self._oauth_access_token = None
        self._oauth_id_token = None

        self._jar = requests.cookies.RequestsCookieJar()

        # Allow up to 5 retries on requests to Okta in case we have network issues
        self._http_client = requests.Session()
        self._http_client.cookies = self._jar

        self.device_token = device_token

        retries = Retry(total=5, backoff_factor=1,
                        allowed_methods=['GET', 'POST'])
        self._http_client.mount('https://', HTTPAdapter(max_retries=retries))

    @property
    def device_token(self):
        return self._http_client.cookies.get('DT')

    @device_token.setter
    def device_token(self, device_token):
        if device_token is not None:
            match = re.search(r'^https://(.*)/?', self._okta_org_url)
            self._http_client.cookies.set('DT', device_token, domain=match.group(1), path='/')

    def set_username(self, username):
        self._username = username

    def set_password(self, password):
        self._password = password

    def set_preferred_mfa_type(self, preferred_mfa_type):
        self._preferred_mfa_type = preferred_mfa_type

    def set_mfa_code(self, mfa_code):
        self._mfa_code = mfa_code

    def set_remember_device(self, remember_device):
        self._remember_device = bool(remember_device)

    def use_oauth_access_token(self, val=True):
        self._use_oauth_access_token = val

    def use_oauth_id_token(self, val=True):
        self._use_oauth_id_token = val

    def stepup_auth(self, embed_link, state_token=None):
        """ Login to Okta using the Step-up authentication flow"""
        flow_state = self._get_initial_flow_state(embed_link, state_token)

        while flow_state.get('apiResponse', {}).get('status') != 'SUCCESS':
            time.sleep(0.5)
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

        while flow_state.get('apiResponse', {}).get('status') != 'SUCCESS':
            time.sleep(0.5)
            flow_state = self._next_login_step(
                flow_state.get('apiResponse', {}).get('stateToken'), flow_state.get('apiResponse'))

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
        return {
            "username": login_response['_embedded']['user']['profile']['login'],
            "session": response.cookies['sid'],
            "device_token": self._http_client.cookies['DT']
        }

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
        response.raise_for_status()

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
            'Content-Type': 'application/json',
        }
        return headers

    def _get_initial_flow_state(self, embed_link, state_token=None):
        """ Starts the authentication flow with Okta"""
        if state_token is None:
            response = self._http_client.get(
                embed_link, allow_redirects=False)
            response.raise_for_status()
            url_parse_results = urlparse(response.headers['Location'])
            state_token = parse_qs(url_parse_results.query)['stateToken'][0]

        response = self._http_client.post(
            self._okta_org_url + '/api/v1/authn',
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        response.raise_for_status()
        return {'stateToken': state_token, 'apiResponse': response.json()}

    def _next_login_step(self, state_token, login_data):
        """ decide what the next step in the login process is"""
        if 'errorCode' in login_data:
            raise errors.GimmeAWSCredsError(
                "LOGIN ERROR: {} | Error Code: {}".format(login_data['errorSummary'], login_data['errorCode']), 2)

        status = login_data['status']

        if status == 'UNAUTHENTICATED':
            return self._login_username_password(state_token, login_data['_links']['next']['href'])
        elif status == 'LOCKED_OUT':
            raise errors.GimmeAWSCredsError("Your Okta access has been locked out due to failed login attempts.", 2)
        elif status == 'MFA_ENROLL':
            raise GimmeAWSCredsMFAEnrollStatus()
        elif status == 'MFA_REQUIRED':
            return self._login_multi_factor(state_token, login_data)
        elif status == 'MFA_CHALLENGE':
            if login_data['_embedded']['factor']['factorType'] == 'u2f':
                return self._check_u2f_result(state_token, login_data)
            if login_data['_embedded']['factor']['factorType'] == 'webauthn':
                return self._check_webauthn_result(state_token, login_data)
            if 'factorResult' in login_data and login_data['factorResult'] == 'WAITING':
                return self._check_push_result(state_token, login_data)
            else:
                return self._login_input_mfa_challenge(state_token, login_data['_links']['next']['href'])
        else:
            raise RuntimeError('Unknown login status: ' + status)

    def _print_correct_answer(self, answer):
        """ prints the correct answer to the additional factor authentication step in Okta Verify"""
        self.ui.info("Additional factor correct answer is: " + str(answer))

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

        if response.status_code == 200:
            pass

        # Handle known Okta error codes
        # ref: https://developer.okta.com/docs/reference/error-codes/#example-errors-listed-by-http-return-code
        elif response.status_code in [400, 401, 403, 404, 409, 429, 500, 501, 503]:
            if response_data['errorCode'] == "E0000004":
                if self.KEYRING_ENABLED:
                    try:
                        self.ui.info("Stored password is invalid, clearing.  Please try again")
                        keyring.delete_password(self.KEYRING_SERVICE, creds['username'])
                    except PasswordDeleteError:
                        pass
            raise errors.GimmeAWSCredsError(
                "LOGIN ERROR: {} | Error Code: {}".format(response_data['errorSummary'], response_data['errorCode']), 2)

        # If the error code isn't one we know how to handle, raise an exception
        else:
            response.raise_for_status()

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
        response.raise_for_status()

        self.ui.info("A verification code has been sent to " + factor['profile']['phoneNumber'])
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
        response.raise_for_status()

        self.ui.info("You should soon receive a phone call at " + factor['profile']['phoneNumber'])
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
        response.raise_for_status()

        self.ui.info("Okta Verify push sent...")
        response_data = response.json()
        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    def _login_input_webauthn_challenge(self, state_token, factor):
        """ Retrieve nonce """
        response = self._http_client.post(
            factor['_links']['verify']['href'],
            json={'stateToken': state_token},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        response.raise_for_status()

        self.ui.info("Challenge with security keys ...")
        response_data = response.json()

        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    @staticmethod
    def get_available_socket():
        """Get available socket, but requesting 0 and allowing OS to provide ephemeral open port"""
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        server_address = s.getsockname()
        return server_address

    def _login_duo_challenge(self, state_token, factor):
        """ Duo MFA challenge """
        passcode = self._mfa_code
        if factor['factorType'] is None:
            # Prompt user for which Duo factor to use
            raise duo.FactorRequired(factor['id'], state_token)

        if factor['factorType'] == "passcode" and not passcode:
            try:
                passcode = self.ui.input("Enter verification code(remember to refresh token between uses): ")
            except Exception:
                raise duo.PasscodeRequired(factor['id'], state_token)

        response_data = self._get_response_data(factor['_links']['verify']['href'], state_token)
        verification = response_data['_embedded']['factor']['_embedded']['verification']
        socket_addr = self.get_available_socket()

        auth = None
        duo_client = duo.Duo(self.ui, verification, state_token, socket_addr, factor['factorType'])
        if factor['factorType'] == "web":
            # Duo Web via local browser
            self.ui.info("Duo required; opening browser...")
            proc = Process(target=duo_client.trigger_web_duo)
            proc.start()
            time.sleep(2)
            webbrowser.open_new('http://{host}:{port}/duo.html'.format(host=socket_addr[0], port=socket_addr[1]))
        elif factor['factorType'] == "passcode":
            # Duo auth with OTP code without a browser
            self.ui.info("Duo required; using OTP...")
            auth = duo_client.trigger_duo(passcode=passcode)
        else:
            # Duo Auth without the browser
            self.ui.info("Duo required; check your phone...")
            auth = duo_client.trigger_duo()

        if auth is not None:
            self.mfa_callback(auth, verification, state_token)
            try:
                response_data = self._get_response_data(response_data.get('_links')['next']['href'], state_token)
                while response_data['status'] != 'SUCCESS':
                    if response_data.get('factorResult', 'REJECTED') == 'REJECTED':
                        self.ui.warning("Duo Push REJECTED")
                        return None

                    if response_data.get('factorResult', 'TIMEOUT') == 'TIMEOUT':
                        self.ui.warning("Duo Push TIMEOUT")
                        return None

                    self.ui.info("Waiting for MFA success...")
                    time.sleep(2)
                    response_data = self._get_response_data(response_data.get('_links')['next']['href'], state_token)

            except KeyboardInterrupt:
                self.ui.warning("User canceled waiting for MFA success.")
                raise

        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

        # return None

    def _get_response_data(self, href, state_token):
        response = self._http_client.post(href,
                                          params={'rememberDevice': self._remember_device},
                                          json={'stateToken': state_token},
                                          headers=self._get_headers(),
                                          verify=self._verify_ssl_certs
                                          )
        response_data = response.json()
        return response_data

    def mfa_callback(self, auth, verification, state_token):
        """Do callback to Okta with the info from the MFA provider
        Args:
            auth: String auth from MFA provider to send in the callback
            verification: Dict of details used in Okta API calls
            state_token: String Okta state token
        """
        app = verification['signature'].split(":")[1]
        response_sig = "{}:{}".format(auth, app)
        callback_params = "stateToken={}&sig_response={}".format(
            state_token, response_sig)

        url = "{}?{}".format(
            verification['_links']['complete']['href'],
            callback_params)
        ret = self._http_client.post(url)
        if ret.status_code != 200:
            raise Exception("Bad status from Okta callback {}".format(
                ret.status_code))

    def _login_multi_factor(self, state_token, login_data):
        """ handle multi-factor authentication with Okta"""
        factor = self._choose_factor(login_data['_embedded']['factors'])
        if factor['provider'] == 'DUO':
            return self._login_duo_challenge(state_token, factor)
        elif factor['factorType'] == 'sms':
            return self._login_send_sms(state_token, factor)
        elif factor['factorType'] == 'call':
            return self._login_send_call(state_token, factor)
        elif factor['factorType'] == 'token:software:totp':
            return self._login_input_mfa_challenge(state_token, factor['_links']['verify']['href'])
        elif factor['factorType'] == 'token':
            return self._login_input_mfa_challenge(state_token, factor['_links']['verify']['href'])
        elif factor['factorType'] == 'push':
            return self._login_send_push(state_token, factor)
        elif factor['factorType'] == 'u2f':
            return self._login_input_webauthn_challenge(state_token, factor)
        elif factor['factorType'] == 'webauthn':
            return self._login_input_webauthn_challenge(state_token, factor)
        elif factor['factorType'] == 'token:hardware':
            return self._login_input_mfa_challenge(state_token, factor['_links']['verify']['href'])

    def _login_input_mfa_challenge(self, state_token, next_url):
        """ Submit verification code for SMS or TOTP authentication methods"""
        pass_code = self._mfa_code
        if pass_code is None:
            pass_code = self.ui.input("Enter verification code: ", hidden=True)
        response = self._http_client.post(
            next_url,
            params={'rememberDevice': self._remember_device},
            json={'stateToken': state_token, 'passCode': pass_code},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        response.raise_for_status()

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
        response.raise_for_status()

        response_data = response.json()

        try:
            if '_embedded' in response_data['_embedded']['factor']:
                if response_data['_embedded']['factor']['_embedded']['challenge']['correctAnswer']:
                    if self._print_correct_answer:
                        self._print_correct_answer(response_data['_embedded']['factor']['_embedded']['challenge']['correctAnswer'])
                        self._print_correct_answer = None
        except:
            pass

        if 'stateToken' in response_data:
            return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
        if 'sessionToken' in response_data:
            return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}

    def _check_u2f_result(self, state_token, login_data):
        # should be deprecated soon as OKTA move forward webauthN
        # just for backward compatibility
        nonce = login_data['_embedded']['factor']['_embedded']['challenge']['nonce']
        credential_id = login_data['_embedded']['factor']['profile']['credentialId']
        app_id = login_data['_embedded']['factor']['profile']['appId']

        verify = FactorU2F(self.ui, app_id, nonce, credential_id)
        try:
            client_data, signature = verify.verify()
        except Exception:
            signature = b'fake'
            client_data = b'fake'

        client_data = str(base64.urlsafe_b64encode(client_data), "utf-8")
        signature_data = str(base64.urlsafe_b64encode(signature), 'utf-8')

        response = self._http_client.post(
            login_data['_links']['next']['href'] + "?rememberDevice=false",
            json={'stateToken': state_token, 'clientData': client_data, 'signatureData': signature_data},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        response.raise_for_status()

        response_data = response.json()
        if 'status' in response_data and response_data['status'] == 'SUCCESS':
            if 'stateToken' in response_data:
                return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
            if 'sessionToken' in response_data:
                return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}
        else:
            return {'stateToken': None, 'sessionToken': None, 'apiResponse': response_data}

    def _check_webauthn_result(self, state_token, login_data):
        """ wait for webauthN challenge """

        nonce = login_data['_embedded']['factor']['_embedded']['challenge']['challenge']
        credential_id = login_data['_embedded']['factor']['profile']['credentialId']

        """ Authenticator """
        webauthn_client = WebAuthnClient(self.ui, self._okta_org_url, nonce, credential_id)
        # noinspection PyBroadException
        try:
            client_data, assertion = webauthn_client.verify()
        except Exception:
            client_data = b'fake'
            assertion = FakeAssertion()

        client_data = str(base64.urlsafe_b64encode(client_data), "utf-8")
        signature_data = base64.b64encode(assertion.signature).decode('utf-8')
        auth_data = base64.b64encode(assertion.auth_data).decode('utf-8')

        response = self._http_client.post(
            login_data['_links']['next']['href'] + "?rememberDevice=false",
            json={'stateToken': state_token, 'clientData': client_data, 'signatureData': signature_data,
                  'authenticatorData': auth_data},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        response.raise_for_status()

        response_data = response.json()
        if 'status' in response_data and response_data['status'] == 'SUCCESS':
            if 'stateToken' in response_data:
                return {'stateToken': response_data['stateToken'], 'apiResponse': response_data}
            if 'sessionToken' in response_data:
                return {'stateToken': None, 'sessionToken': response_data['sessionToken'], 'apiResponse': response_data}
        else:
            return {'stateToken': None, 'sessionToken': None, 'apiResponse': response_data}

    def get_saml_response(self, url, auth_session = None):
        """ return the base64 SAML value object from the SAML Response"""
        response = self._http_client.get(url, verify=self._verify_ssl_certs)
        response.raise_for_status()

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
            state_token = self._extract_state_token_from_http_response(response)
            if state_token:
                api_response = self.stepup_auth(url, state_token)
                if 'sessionToken' in api_response:
                    saml_request_url = url + '?sessionToken=' + api_response['sessionToken']
                else:
                    saml_request_url = url + '?stateToken=' + api_response['_links']['next']['href']

                saml_response = self.get_saml_response(saml_request_url)
                return saml_response

            saml_error = 'Did not receive SAML Response after successful authentication [' + url + ']'
            if saml_soup.find(class_='error-content') is not None:
                saml_error += '\n' + saml_soup.find(class_='error-content').get_text()

            raise RuntimeError(saml_error)

        return {'SAMLResponse': saml_response, 'RelayState': relay_state, 'TargetUrl': form_action}

    def check_kwargs(self, kwargs):
        if self._use_oauth_access_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        if self._use_oauth_id_token is True:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers']['Authorization'] = "Bearer {}".format(self._oauth_access_token)

        return kwargs

    def get(self, url, **kwargs):
        """ Retrieve resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        return self._http_client.get(url, **parameters)

    def post(self, url, **kwargs):
        """ Create resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        return self._http_client.post(url, **parameters)

    def put(self, url, **kwargs):
        """ Modify resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        return self._http_client.put(url, **parameters)

    def delete(self, url, **kwargs):
        """ Delete resource that is protected by Okta """
        parameters = self.check_kwargs(kwargs)
        return self._http_client.delete(url, **parameters)

    def _choose_factor(self, factors):
        """ gets a list of available authentication factors and
        asks the user to select the factor they want to use """

        self.ui.info("Multi-factor Authentication required.")

        # filter the factor list down to just the types specified in preferred_mfa_type
        preferred_factors = []
        # even though duo supports both passcode and push, okta only lists web as an available factor. This if statement
        # adds the additional supported factors only if the provider is duo, and the web factor is the only one provided
        if len(factors) == 1 and factors[0].get('provider') == 'DUO' and factors[0].get('factorType') == 'web':
            push = copy.deepcopy(factors[0])
            push['factorType'] = "push"
            factors.append(push)
            passcode = copy.deepcopy(factors[0])
            passcode['factorType'] = "passcode"
            factors.append(passcode)
        if self._preferred_mfa_type is not None:
            preferred_factors = list(filter(lambda item: item['factorType'] == self._preferred_mfa_type, factors))
            # If the preferred factor isn't in the list of available factors, we'll let the user know before
            # prompting to select another.
            if not preferred_factors:
                self.ui.notify('Preferred factor type of {} not available.'.format(self._preferred_mfa_type))

        if len(preferred_factors) == 1:
            factor_name = self._build_factor_name(preferred_factors[0])
            self.ui.info(factor_name + ' selected')
            selection = factors.index(preferred_factors[0])
        elif len(factors) == 1:
            factor_name = self._build_factor_name(factors[0])
            print("Using the only authentication factor configured: {}.".format(factor_name))
            selection = factors.index(factors[0])
        else:
            self.ui.info("Pick a factor:")
            # print out the factors and let the user select
            for i, factor in enumerate(factors):
                factor_name = self._build_factor_name(factor)
                if factor_name != "":
                    self.ui.info('[{}] {}'.format(i, factor_name))
            selection = self._get_user_int_factor_choice(len(factors))

        # make sure the choice is valid
        if selection is None:
            raise errors.GimmeAWSCredsError("You made an invalid selection")

        return factors[selection]

    def _get_user_int_factor_choice(self, max_int, max_retries=5):
        for _ in range(max_retries):
            value = self.ui.input('Selection: ')
            try:
                selection = int(value.strip())
            except ValueError:
                self.ui.warning(
                    'Invalid selection {!r}, must be an integer value.'.format(value)
                )
                continue

            if 0 <= selection <= max_int:
                return selection
            else:
                self.ui.warning(
                    'Selection {!r} out of range <0, {}>'.format(selection, max_int)
                )

        return None

    def _build_factor_name(self, factor):
        """ Build the display name for a MFA factor based on the factor type"""
        if factor['provider'] == 'DUO':
            return factor['factorType'] + ": " + factor['provider'].capitalize()
        elif factor['factorType'] == 'push':
            return "Okta Verify App: " + factor['profile']['deviceType'] + ": " + factor['profile']['name']
        elif factor['factorType'] == 'sms':
            return factor['factorType'] + ": " + factor['profile']['phoneNumber']
        elif factor['factorType'] == 'call':
            return factor['factorType'] + ": " + factor['profile']['phoneNumber']
        elif factor['factorType'] == 'token:software:totp':
            return factor['factorType'] + "( " + factor['provider'] + " ) : " + factor['profile']['credentialId']
        elif factor['factorType'] == 'token':
            return factor['factorType'] + ": " + factor['profile']['credentialId']
        elif factor['factorType'] == 'u2f':
            return factor['factorType'] + ": " + factor['factorType']
        elif factor['factorType'] == 'webauthn':
            factor_name = None
            try:
                registered_authenticators = RegisteredAuthenticators(self.ui)
                credential_id = websafe_decode(factor['profile']['credentialId'])
                factor_name = registered_authenticators.get_authenticator_user(credential_id)
            except Exception:
                pass

            default_factor_name = factor['profile'].get('authenticatorName') or factor['factorType']
            factor_name = factor_name or default_factor_name

            return factor['factorType'] + ": " + factor_name
        elif factor['factorType'] == 'token:hardware':
            return factor['factorType'] + ": " + factor['provider']

        else:
            return "Unknown MFA type: " + factor['factorType']

    def _get_username_password_creds(self):
        """Get's creds for Okta login from the user."""

        if self._username is None:
            # ask the user
            self._username = self.ui.input('Username: ')
        username = self._username

        password = self._password
        if not password and self.KEYRING_ENABLED:
            try:
                # If the OS supports a keyring, offer to save the password
                password = keyring.get_password(self.KEYRING_SERVICE, username)
                self.ui.info("Using password from keyring for {}".format(username))
            except RuntimeError:
                self.ui.warning("Unable to get password from keyring.")
        if not password:
            # Set prompt to include the user name, since username could be set
            # via OKTA_USERNAME env and user might not remember.
            for x in range(0, 5):
                passwd_prompt = "Okta Password for {}: ".format(username)
                password = getpass.getpass(prompt=passwd_prompt)
                if len(password) > 0:
                    break

            if self.KEYRING_ENABLED:
                # If the OS supports a keyring, offer to save the password
                if self.ui.input("Do you want to save this password in the keyring? (y/N) ") == 'y':
                    try:
                        keyring.set_password(self.KEYRING_SERVICE, username, password)
                        self.ui.info("Password for {} saved in keyring.".format(username))
                    except RuntimeError as err:
                        self.ui.warning("Failed to save password in keyring: " + str(err))

        if not password:
            raise errors.GimmeAWSCredsError('Password was not provided. Exiting.')

        return {'username': username, 'password': password}

    def setup_fido_authenticator(self):
        setup_fido_authenticator_url = self._okta_org_url + '/user/settings/factors/setup?factorType=FIDO_WEBAUTHN'

        response = self._http_client.get(setup_fido_authenticator_url, headers=self._get_headers(),
                                         verify=self._verify_ssl_certs)
        response.raise_for_status()

        parsed_url = urlparse(response.url)
        if parsed_url and parsed_url.path == '/user/verify_password':
            response = self._verify_password(response)

        state_token = self._extract_state_token_from_http_response(response)
        if not state_token:
            raise RuntimeError('Could not extract state token from http response')

        try:
            self.stepup_auth(setup_fido_authenticator_url, state_token)
        except errors.GimmeAWSCredsMFAEnrollStatus:
            # Expected while adding a new fido authenticator
            pass

        response = self._http_client.get(setup_fido_authenticator_url, json={'stateToken': state_token},
                                         headers=self._get_headers(), verify=self._verify_ssl_certs)
        response.raise_for_status()

        state_token = self._extract_state_token_from_http_response(response)
        credential_id, user_name = self._activate_webauthn_factor(state_token)

        self.ui.info('\nAuthenticator setup finished successfully.')
        return credential_id, user_name

    def _verify_password(self, verify_password_page_response):
        creds = self._get_username_password_creds()

        saml_soup = BeautifulSoup(verify_password_page_response.text, "html.parser")
        token_elem = saml_soup.find(id='_xsrfToken')
        if not token_elem:
            raise RuntimeError('Could not find expected xsrf token in password verification page: id="_xsrfToken"')

        if not token_elem.has_attr('value'):
            raise RuntimeError('Could not find expected "value" attribute for xsrf dom element in password '
                               'verification page')

        xsrf_token = token_elem.get('value')
        if not xsrf_token:
            raise RuntimeError('Could not find non-blank "value" attribute for xsrf dom element in password'
                               'verification page')

        headers = self._get_headers()
        # Must be form urlencoded
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        data = '_xsrfToken={xsrf_token}&password={password}'.format(xsrf_token=xsrf_token, password=creds['password'])
        response = self._http_client.post(self._okta_org_url + '/user/verify_password',
                                          data=data, headers=headers, verify=self._verify_ssl_certs)
        response.raise_for_status()

        response = self._http_client.get(
            self._okta_org_url + '/login/second-factor?fromURI=%2Fenduser%2Fsettings&forcePrompt=true&hideBgImage=true',
            headers=self._get_headers(), verify=self._verify_ssl_certs)
        response.raise_for_status()

        return response

    def _activate_webauthn_factor(self, state_token):
        enrollment_response = self._enroll_factor(state_token)
        response_json = enrollment_response.json()

        next_link = response_json['_links']['next']
        if next_link['name'] != 'activate':
            raise RuntimeError('Expected next link to be an activation link, actually got: ' + next_link["name"])

        factor_obj = response_json['_embedded']['factor']
        activation_obj = factor_obj['_embedded']['activation']

        challenge = activation_obj.get('challenge')
        user_obj = activation_obj.get('user', {})

        webauthn_client = WebAuthnClient(self.ui, self._okta_org_url, challenge)
        client_data_json, attestation = webauthn_client.make_credential(user_obj)
        client_data = str(base64.urlsafe_b64encode(client_data_json), 'utf-8')
        attestation_data = str(base64.urlsafe_b64encode(attestation), 'utf-8')

        response = self._http_client.post(
            next_link['href'],
            json={"stateToken": state_token, "clientData": client_data, "attestation": attestation_data},
            headers=self._get_headers(), verify=self._verify_ssl_certs)
        response.raise_for_status()

        session_token = response.json()['sessionToken']
        redirect_url = quote(self._okta_org_url + '/enduser/settings?enrolledFactor=FIDO_WEBAUTHN')

        response = self._http_client.get(
            self._okta_org_url + '/login/sessionCookieRedirect?checkAccountSetupComplete=true&'
                                 'token={session_token}&redirectUrl={redirect_url}'.format(session_token=session_token,
                                                                                           redirect_url=redirect_url),
            headers=self._get_headers(), verify=self._verify_ssl_certs)
        response.raise_for_status()

        return attestation.auth_data.credential_data.credential_id, user_obj.get('name', 'gimme-aws-creds')

    def _enroll_factor(self, state_token):
        factors = self._introspect_factors(state_token)
        if len(factors) != 1:
            raise RuntimeError('Expected the state token to request enrollment for a specific factor')

        # The state token should be set to return a specific factor
        webauthn_factor = factors[0]
        response = self._http_client.post(
            webauthn_factor['_links']['enroll']['href'],
            json={"stateToken": state_token, "factorType": webauthn_factor['factorType'],
                  "provider": webauthn_factor['provider']},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        response.raise_for_status()

        return response

    def _introspect_factors(self, state_token):
        response = self._http_client.post(self._okta_org_url + '/api/v1/authn/introspect',
                                          json={"stateToken": state_token}, headers=self._get_headers(),
                                          verify=self._verify_ssl_certs)
        response.raise_for_status()
        factors = response.json()['_embedded']['factors']
        if not factors:
            raise RuntimeError('Could not introspect factors')

        return factors

    @staticmethod
    def _extract_state_token_from_http_response(http_res):
        saml_soup = BeautifulSoup(http_res.text, "html.parser")
        
        mfa_string = (
            'Dodatečné ověření',
            'Ekstra verificering',
            'Zusätzliche Bestätigung',
            'Πρόσθετη επαλήθευση',
            'Extra Verification',
            'Verificación adicional',
            'Lisätodennus',
            'Vérification supplémentaire',
            'Extra ellenőrzés',
            'Verifikasi Tambahan',
            'Verifica aggiuntiva',
            '追加認証',
            '추가 확인',
            'Penentusahan Tambahan',
            'Ekstra verifisering',
            'Extra verificatie',
            'Dodatkowa weryfikacja',
            'Verificação extra',
            'Verificare suplimentară',
            'Дополнительная проверка',
            'Extra verifiering',
            'การตรวจสอบพิเศษ',
            'Ekstra Doğrulama',
            'Додаткова верифікація',
            'Xác minh bổ sung',
            '额外验证',
            '額外驗證'
        )

        if hasattr(saml_soup.title, 'string') and saml_soup.title.string.endswith(mfa_string):
            # extract the stateToken from the Javascript code in the page and step up to MFA
            # noinspection PyTypeChecker
            state_token = decode(re.search(r"var stateToken = '(.*)';", http_res.text).group(1), "unicode-escape")
            return state_token

        for tag in saml_soup.find_all('body'):
            # checking all the tags in body tag for Extra Verification string
            if re.search(r"Extra Verification", tag.text, re.IGNORECASE):
                # extract the stateToken from response (form action) instead of javascript variable
                # noinspection PyTypeChecker
                pre_state_token = decode(re.search(r"stateToken=(.*?[ \"])", http_res.text).group(1), "unicode-escape")
                state_token = pre_state_token.rstrip('\"')
                return state_token

        return None
