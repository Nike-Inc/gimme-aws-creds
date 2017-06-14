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

        # self._get_aws_info()

    def set_username(self, username):
        self._username = username

    def login(self, embed_link):
        """ set the user credentials"""
        self._server_embed_link = embed_link
        self._start_login_flow()
        self._get_aws_account_info()

    def _get_headers(self):
        """sets the default headers"""
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json' }
        return headers

    def _start_login_flow(self):
        """ gets the starts the authentication flow with Okta"""
        response = requests.get(self._server_embed_link , allow_redirects=False)
        url_parse_results = urlparse(response.headers['Location'])
        stateToken =  parse_qs(url_parse_results.query)['stateToken'][0]

        response = requests.post(
            self._okta_org_url + '/authn',
            json={'stateToken': stateToken},
            headers=self._get_headers()
        )
        self._next_login_step(stateToken, response.json())

    def _login_username_password(self, stateToken, url):
        """ login to Okta with a username and password"""
        creds = self._get_username_password_creds()
        response = requests.post(
            url,
            json={'stateToken': stateToken, 'username': creds['username'], 'password': creds['password']},
            headers=self._get_headers()
        )
        self._next_login_step(stateToken, response.json())

    def _login_get_saml_response(self, url):
        """ return the base64 SAML value object from the SAML Response"""
        response = requests.get(url, verify=self._verify_ssl_certs)

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

    def _get_aws_account_info(self):
        s = requests.Session()
        s.post(
            self._login_saml_form_action,
            data = {'SAMLResponse':self._login_saml_response, 'RelayState':self._login_saml_relay_state},
            verify = self._verify_ssl_certs
        )

        response = s.get('https://localhost:8443/api/v1/accounts', verify = self._verify_ssl_certs)

        print(self._login_saml_form_action)

        print(response.text)

        exit()


    # def get_app_links(self):
    #     """ return appLinks obejct for the user """
    #     headers = self._get_headers()
    #
    #     response = requests.get(
    #         self._okta_org_url + '/users/' + self._user_id + '/appLinks',
    #         headers=headers,
    #         verify=True
    #     )
    #     app_resp = json.loads(response.text)
    #
    #     # create a list from appName = amazon_aws
    #     apps = []
    #     for app in app_resp:
    #         if app['appName'] == 'amazon_aws':
    #             apps.append(app)
    #
    #     if 'errorCode' in app_resp:
    #         print("APP LINK ERROR: " + app_resp['errorSummary'], "Error Code ", app_resp['errorCode'])
    #         sys.exit(2)
    #
    #     return apps
    #
    # def get_app(self):
    #     """ gets a list of available apps and
    #     ask the user to select the app they want
    #     to assume a roles for and returns the selection
    #     """
    #     app_resp = self.get_app_links()
    #     print("Pick an app:")
    #     # print out the apps and let the user select
    #     for i, app in enumerate(app_resp):
    #         print('[', i, ']', app["label"])
    #
    #     selection = input("Selection: ")
    #
    #     # make sure the choice is valid
    #     if int(selection) > len(app_resp):
    #         print("You selected an invalid selection")
    #         sys.exit(1)
    #
    #     # delete
    #     return app_resp[int(selection)]["label"]
    #
    # def get_role(self, aws_appname):
    #     """ gets a list of available roles and
    #     ask the user to select the role they want
    #     to assume and returns the selection
    #     """
    #     # get available roles for the AWS app
    #     headers = self._get_headers()
    #     response = requests.get(
    #         self._okta_org_url + '/apps/?filter=user.id+eq+\"' +
    #         self._user_id + '\"&expand=user/' + self._user_id + '&limit=200',
    #         headers=headers,
    #         verify=True
    #     )
    #     role_resp = json.loads(response.text)
    #
    #     # Check if this is a valid response
    #     if 'errorCode' in role_resp:
    #         print("ERROR: " + role_resp['errorSummary'], "Error Code ", role_resp['errorCode'])
    #         sys.exit(2)
    #
    #     # print out roles for the app and let the uesr select
    #     for app in role_resp:
    #         if app['label'] == aws_appname:
    #             print("Pick a role:")
    #             roles = app['_embedded']['user']['profile']['samlRoles']
    #
    #             for i, role in enumerate(roles):
    #                 print('[', i, ']:', role)
    #             selection = input("Selection: ")
    #
    #             # make sure the choice is valid
    #             if int(selection) > len(roles):
    #                 print("You selected an invalid selection")
    #                 sys.exit(1)
    #
    #             return roles[int(selection)]
    #
    # def get_app_url(self, aws_appname):
    #     """ return the app link json for select aws app """
    #     app_resp = self.get_app_links()
    #
    #     for app in app_resp:
    #         if app['label'] == 'AWS_API':
    #             print(app['linkUrl'])
    #         if app['label'] == aws_appname:
    #             return app
    #
    #     print("ERROR app not found:", aws_appname)
    #     sys.exit(2)
    #
    # def get_idp_arn(self, app_id):
    #     """ return the PrincipalArn based on the app instance id """
    #     headers = self._get_headers()
    #     response = requests.get(
    #         self._okta_org_url + '/apps/' + app_id,
    #         headers=headers,
    #         verify=True
    #     )
    #     app_resp = json.loads(response.text)
    #     return app_resp['settings']['app']['identityProviderArn']
    #
    # def get_role_arn(self, link_url, aws_rolename):
    #     """ return the role arn for the selected role """
    #     # decode the saml so we can find our arns
    #     # https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/
    #     aws_roles = []
    #     root = et.fromstring(base64.b64decode(self.get_saml_assertion(link_url)))
    #
    #     for saml2attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
    #         if saml2attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role':
    #             for saml2attributevalue in saml2attribute.iter(
    #                     '{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
    #                 aws_roles.append(saml2attributevalue.text)
    #
    #     # grab the role ARNs that matches the role to assume
    #     for aws_role in aws_roles:
    #         chunks = aws_role.split(',')
    #         if aws_rolename in chunks[1]:
    #             return chunks[1]
    #
    #     # if you got this far something went wrong
    #     print("ERROR no ARN found for", aws_rolename)
    #     sys.exit(2)
    #
    # def get_saml_assertion(self, app_url):
    #     """return the base64 SAML value object from the SAML Response"""
    #     if self._saml_assertion is None:
    #         response = requests.get(
    #             app_url + '/?sessionToken=' + self._session_token,
    #             verify=True
    #         )
    #
    #         saml_soup = BeautifulSoup(response.text, "html.parser")
    #         for inputtag in saml_soup.find_all('input'):
    #             if inputtag.get('name') == 'SAMLResponse':
    #                 self._saml_assertion = inputtag.get('value')
    #
    #     return self._saml_assertion



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
