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
import json
import sys
import getpass
import xml.etree.ElementTree as et
from urllib.parse import urlparse
from urllib.parse import parse_qs

import requests
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

        self._server_embed_link = None
        self._username = None

        self._login_saml_response = None
        self._login_saml_form_action = None
        self._login_saml_relay_state = None

        self.aws_access = None

        self.req_session = requests.Session()

    def set_username(self, username):
        self._username = username

    def login(self, embed_link, gimme_creds_server_url):
        """ Login to Okta and request data from the gimme-creds-server"""
        self._server_embed_link = embed_link
        self._start_login_flow()
        self._get_aws_account_info(gimme_creds_server_url)

    def _get_headers(self):
        """sets the default headers"""
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json' }
        return headers

    def _start_login_flow(self):
        """ gets the starts the authentication flow with Okta"""
        response = self.req_session.get(self._server_embed_link , allow_redirects=False)
        url_parse_results = urlparse(response.headers['Location'])
        stateToken =  parse_qs(url_parse_results.query)['stateToken'][0]

        response = self.req_session.post(
            self._okta_org_url + '/authn',
            json={'stateToken': stateToken},
            headers=self._get_headers()
        )
        self._next_login_step(stateToken, response.json())

    def _login_username_password(self, stateToken, url):
        """ login to Okta with a username and password"""
        creds = self._get_username_password_creds()
        response = self.req_session.post(
            url,
            json={'stateToken': stateToken, 'username': creds['username'], 'password': creds['password']},
            headers=self._get_headers()
        )
        self._next_login_step(stateToken, response.json())

    def _login_get_saml_response(self, url):
        """ return the base64 SAML value object from the SAML Response"""
        response = self.req_session.get(url, verify=self._verify_ssl_certs)

        saml_soup = BeautifulSoup(response.text, "html.parser")
        self._login_saml_form_action = saml_soup.find('form', id='appForm').get('action')
        for inputtag in saml_soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                self._login_saml_response = inputtag.get('value')
            elif inputtag.get('name') == 'RelayState':
                self._login_saml_relay_state = inputtag.get('value')

    def _next_login_step(self, stateToken, login_data):
        """ decide what the next step in the login process is"""
        if 'errorCode' in login_data:
            print("LOGIN ERROR: " + login_data['errorSummary'], "Error Code ", login_data['errorCode'])
            sys.exit(2)

        status = login_data['status']

        if status == 'UNAUTHENTICATED':
            self._login_username_password(stateToken, login_data['_links']['next']['href'])
        elif status == 'SUCCESS':
            self._login_get_saml_response(login_data['_links']['next']['href'])
        elif status == 'MFA_ENROLL':
            print("You must enroll in MFA before using this tool.")
            sys.exit(2)
        elif status == 'MFA_REQUIRED':
            raise NotImplementedError('Okta MFA not yet implemented.')
        else:
            raise RuntimeError('Unknown login status: ' + status)

    def _get_aws_account_info(self, gimme_creds_server_url):
        """ Submit the SAMLResponse and retreive the user's AWS accounts from the gimme_creds_server"""
        self.req_session.post(
            self._login_saml_form_action,
            data = {'SAMLResponse':self._login_saml_response, 'RelayState':self._login_saml_relay_state},
            verify = self._verify_ssl_certs
        )

        api_url = gimme_creds_server_url + '/api/v1/accounts'
        response = self.req_session.get(api_url, verify = self._verify_ssl_certs)
        self.aws_access = response.json()

        # Throw an error if we didn't get any accounts back
        if self.aws_access == []:
            print("No AWS accounts found")
            exit()

    def choose_app(self):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection
        """
        #app_resp = self.get_app_links()
        print("Pick an app:")
        # print out the apps and let the user select
        for i, app in enumerate(self.aws_access):
            print('[', i, ']', app["name"])

        selection = input("Selection: ")

        # make sure the choice is valid
        if int(selection) > len(self.aws_access):
            print("You selected an invalid selection")
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
            print("You selected an invalid selection")
            sys.exit(1)

        return app_info['roles'][int(selection)]

    def get_saml_assertion(self, app_url):
        """return the base64 SAML value object from the SAML Response"""
        response = self.req_session.get(
            app_url,
            verify=self._verify_ssl_certs
        )

        # parse the SAML response from the HTML
        saml_soup = BeautifulSoup(response.text, "html.parser")
        for inputtag in saml_soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                self._saml_assertion = inputtag.get('value')

        return self._saml_assertion

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
