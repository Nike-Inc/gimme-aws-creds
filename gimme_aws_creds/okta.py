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
import time
import base64
import json
import sys
import getpass
import xml.etree.ElementTree as et
from urllib.parse import urlparse
from urllib.parse import parse_qs

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from bs4 import BeautifulSoup

class OktaClient(object):
    """
       The Okta Client Class performes the necessary API
       calls to Okta to get temporary AWS credentials. An
       Okta API key and URL must be provided.
    """

    def __init__(self, okta_org_url, verify_ssl_certs=True):
        """
        :param okta_org_url: Base URL string for Okta IDP.
        :param verify_ssl_certs: Enable/disable SSL verification
        """
        self._okta_org_url = okta_org_url
        self._verify_ssl_certs = verify_ssl_certs

        if (verify_ssl_certs is False):
            requests.packages.urllib3.disable_warnings()

        self._server_embed_link = None
        self._username = None

        self.aws_access = None

        # Allow up to 5 retries on requests to Okta in case we have network issues
        self.req_session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, method_whitelist=['GET', 'POST'])
        self.req_session.mount('https://', HTTPAdapter(max_retries=retries))

    def set_username(self, username):
        self._username = username

    def login(self, embed_link, gimme_creds_server_url):
        """ Login to Okta and request data from the gimme-creds-server"""
        self._server_embed_link = embed_link

        flowState = self._get_state_token()

        while flowState['apiResponse']['status'] != 'SUCCESS':
            flowState = self._next_login_step(flowState['stateToken'], flowState['apiResponse'])

        print("Authentication Success! Getting AWS Accounts...")
        samlResponse = self.get_saml_response(flowState['apiResponse']['_links']['next']['href'])

        self._get_aws_account_info(gimme_creds_server_url, samlResponse)

    def _get_headers(self):
        """sets the default headers"""
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json' }
        return headers

    def _get_state_token(self):
        """ gets the starts the authentication flow with Okta"""
        response = self.req_session.get(self._server_embed_link , allow_redirects=False)
        url_parse_results = urlparse(response.headers['Location'])
        stateToken =  parse_qs(url_parse_results.query)['stateToken'][0]

        response = self.req_session.post(
            self._okta_org_url + '/authn',
            json={'stateToken': stateToken},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        return {'stateToken': stateToken, 'apiResponse': response.json()}

    def _next_login_step(self, stateToken, login_data):
        """ decide what the next step in the login process is"""
        if 'errorCode' in login_data:
            print("LOGIN ERROR: " + login_data['errorSummary'], "Error Code ", login_data['errorCode'])
            sys.exit(2)

        status = login_data['status']

        if status == 'UNAUTHENTICATED':
            return self._login_username_password(stateToken, login_data['_links']['next']['href'])
        elif status == 'MFA_ENROLL':
            print("You must enroll in MFA before using this tool.")
            sys.exit(2)
        elif status == 'MFA_REQUIRED':
            return self._login_multi_factor(stateToken, login_data)
        elif status == 'MFA_CHALLENGE':
            if 'factorResult' in login_data and login_data['factorResult'] == 'WAITING':
                return self._check_push_result(stateToken, login_data)
            else:
                return self._login_input_mfa_challenge(stateToken, login_data['_links']['next']['href'])
        else:
            raise RuntimeError('Unknown login status: ' + status)

    def _login_username_password(self, stateToken, url):
        """ login to Okta with a username and password"""
        creds = self._get_username_password_creds()
        response = self.req_session.post(
            url,
            json={'stateToken': stateToken, 'username': creds['username'], 'password': creds['password']},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        login_data = response.json()
        if 'errorCode' in login_data:
            print("LOGIN ERROR: " + login_data['errorSummary'], "Error Code ", login_data['errorCode'])
            sys.exit(2)

        return {'stateToken': stateToken, 'apiResponse': login_data}

    def _login_send_sms(self, stateToken, factor):
        """ Send SMS message for second factor authentication"""
        response = self.req_session.post(
            factor['_links']['verify']['href'],
            json={'stateToken': stateToken},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        print("A verification code has been sent to " + factor['profile']['phoneNumber'])
        return {'stateToken': stateToken, 'apiResponse': response.json() }

    def _login_send_push(self, stateToken, factor):
        """ Send 'push' for the Okta Verify mobile app """
        response = self.req_session.post(
            factor['_links']['verify']['href'],
            json={'stateToken': stateToken},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )

        print("Okta Verify push sent...")
        return {'stateToken': stateToken, 'apiResponse': response.json()}


    def _login_multi_factor(self, stateToken, login_data):
        """ handle multi-factor authentication with Okta"""
        factor = self._choose_factor(login_data['_embedded']['factors'])
        if factor['factorType'] == 'sms':
            return self._login_send_sms(stateToken, factor)
        elif factor['factorType'] == 'token:software:totp':
            return self._login_input_mfa_challenge(stateToken, factor['_links']['verify']['href'])
        elif factor['factorType'] == 'push':
            return self._login_send_push(stateToken, factor)

    def _login_input_mfa_challenge(self, stateToken, next_url):
        """ Submit verification code for SMS or TOTP authentication methods"""
        passCode = input("Enter verification code: ")
        response = self.req_session.post(
            next_url,
            json={'stateToken': stateToken, 'passCode': passCode},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        return {'stateToken': stateToken, 'apiResponse': response.json()}

    def _check_push_result(self, stateToken, login_data):
        """ Check Okta API to see if the push request has been responded to"""
        time.sleep(1)
        response = self.req_session.post(
            login_data['_links']['next']['href'],
            json={'stateToken': stateToken},
            headers=self._get_headers(),
            verify=self._verify_ssl_certs
        )
        return {'stateToken': stateToken, 'apiResponse': response.json()}

    def get_saml_response(self, url):
        """ return the base64 SAML value object from the SAML Response"""
        response = self.req_session.get(url, verify=self._verify_ssl_certs)

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
            raise RuntimeError('Did not receive SAML Response after successful authentication [' + url + ']')

        return {'SAMLResponse': saml_response, 'RelayState': relay_state, 'TargetUrl': form_action}

    def _get_aws_account_info(self, gimme_creds_server_url, saml_data):
        """ Submit the SAMLResponse and retreive the user's AWS accounts from the gimme_creds_server"""
        self.req_session.post(
            saml_data['TargetUrl'],
            data = saml_data,
            verify = self._verify_ssl_certs
        )

        api_url = gimme_creds_server_url + '/api/v1/accounts'
        response = self.req_session.get(api_url, verify = self._verify_ssl_certs)

        self.aws_access = response.json()

        # Throw an error if we didn't get any accounts back
        if self.aws_access == []:
            print("No AWS accounts found")
            exit()

    def _choose_factor(self, factors):
        """ gets a list of available authentication factors and
        asks the user to select the factor they want to use """

        print("Multi-factor Authentication required.")
        print("Pick a factor:")
        # print out the factors and let the user select
        for i, factor in enumerate(factors):
            factorName = self._build_factor_name(factor)
            if factorName != '' :
                print('[', i, ']', factorName)

        selection = input("Selection: ")

        # make sure the choice is valid
        if int(selection) > len(factors):
            print("You made an invalid selection")
            sys.exit(1)

        return factors[int(selection)]

    def _build_factor_name(self, factor):
        """ Build the display name for a MFA factor based on the factor type"""
        if factor['factorType'] == 'push':
            return "Okta Verify App: " + factor['profile']['deviceType'] + ": " + factor['profile']['name']
        elif factor['factorType'] == 'sms':
            return factor['factorType'] + ": " + factor['profile']['phoneNumber']
        elif factor['factorType'] == 'token:software:totp':
            return factor['factorType'] + ": " + factor['profile']['credentialId']
        else:
            print("Unknown MFA type: " + factor['factorType'])
            return ""

    def choose_app(self):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection
        """

        print("Pick an app:")
        # print out the apps and let the user select
        for i, app in enumerate(self.aws_access):
            print('[', i, ']', app["name"])

        selection = input("Selection: ")

        # make sure the choice is valid
        if int(selection) > len(self.aws_access):
            print("You made an invalid selection")
            sys.exit(1)

        return self.aws_access[int(selection)]

    def get_app_by_name(self, appname):
        """ returns the app with the matching name"""
        for i, app in enumerate(self.aws_access):
            if app["name"] == appname:
                return app

    def get_role_by_name(self, app_info, rolename):
        """ returns the role with the matching name"""
        for i, role in enumerate(app_info['roles']):
            if role["name"] == rolename:
                return role

    def choose_role(self, app_info):
        """ gets a list of available roles and
        asks the user to select the role they want to assume
        """

        print("Pick a role:")
        # print out the roles and let the user select
        for i, role in enumerate(app_info['roles']):
            print('[', i, ']', role["name"])

        selection = input("Selection: ")

        # make sure the choice is valid
        if int(selection) > len(app_info['roles']):
            print("You made an invalid selection")
            sys.exit(1)

        return app_info['roles'][int(selection)]

    def _get_username_password_creds(self):
        """Get's creds for Okta login from the user."""
        # Check to see if the username arg has been set, if so use that
        if self._username is not None:
            username = self._username
        # Otherwise just ask the user
        else:
            username = input("Email address: ")
        # Set prompt to include the user name, since username could be set
        # via OKTA_USERNAME env and user might not remember.
        passwd_prompt = "Password for {}: ".format(username)
        password = getpass.getpass(prompt=passwd_prompt)
        if len(password) == 0:
            print("Password must be provided.")
            sys.exit(1)
        creds = {'username': username, 'password': password }

        return creds
