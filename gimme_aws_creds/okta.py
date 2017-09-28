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
import xml.etree.ElementTree as et

import requests
from bs4 import BeautifulSoup


class OktaClient(object):
    """
       The Okta Client Class performes the necessary API
       calls to Okta to get temporary AWS credentials. An
       Okta API key and URL must be provided.
    """

    def __init__(self, idp_entry_url, api_key, username, password):
        """
        :param idp_entry_url: Base URL string for Okta IDP.
        :param api_key: Okta API key string.
        :param username: User's username string.
        :param password: User's password string.
        """
        self._okta_api_key = api_key
        self._idp_entry_url = idp_entry_url

        self._user_id = None
        self._session_token = None
        self._saml_assertion = None

        # Unfortunately we have to store credentials in memory since we'll need them more than once.
        self._username = username
        self._password = password

        self._get_login_response()

    def _get_headers(self):
        """sets the default header"""
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'SSWS ' + self._okta_api_key}
        return headers

    def _get_login_response(self):
        """ gets the login response from Okta and returns the json response"""
        headers = self._get_headers()
        response = requests.post(
            self._idp_entry_url + '/authn',
            json={'username': self._username, 'password': self._password},
            headers=headers
        )

        login_data = response.json()

        if 'errorCode' in login_data:
            print("LOGIN ERROR: " + login_data['errorSummary'], "Error Code ", login_data['errorCode'])
            sys.exit(2)
        elif login_data['status'] == 'MFA_REQUIRED':
            raise NotImplementedError('Okta MFA not yet implemented.')

        self._user_id = login_data['_embedded']['user']['id']
        self._session_token = login_data['sessionToken']

    def get_app_links(self):
        """ return appLinks obejct for the user """
        headers = self._get_headers()

        response = requests.get(
            self._idp_entry_url + '/users/' + self._user_id + '/appLinks',
            headers=headers,
            verify=True
        )
        app_resp = json.loads(response.text)

        # create a list from appName = amazon_aws
        apps = []
        for app in app_resp:
            if app['appName'] == 'amazon_aws':
                apps.append(app)

        if 'errorCode' in app_resp:
            print("APP LINK ERROR: " + app_resp['errorSummary'], "Error Code ", app_resp['errorCode'])
            sys.exit(2)

        return apps

    def get_app(self):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection
        """
        app_resp = self.get_app_links()
        print("Pick an app:")
        # print out the apps and let the user select
        for i, app in enumerate(app_resp):
            print('[', i, ']', app["label"])

        selection = input("Selection: ")

        # make sure the choice is valid
        if int(selection) > len(app_resp):
            print("You selected an invalid selection")
            sys.exit(1)

        # delete
        return app_resp[int(selection)]["label"]

    def get_role(self, aws_appname):
        """ gets a list of available roles and
        ask the user to select the role they want
        to assume and returns the selection
        """
        # get available roles for the AWS app
        headers = self._get_headers()
        print("Getting available roles for " + aws_appname)
        response = requests.get(
            self._idp_entry_url + '/apps/?filter=user.id+eq+\"' +
            self._user_id + '\"&expand=user/' + self._user_id + '&limit=200',
            headers=headers,
            verify=True
        )
        role_resp = json.loads(response.text)

        # Check if this is a valid response
        if 'errorCode' in role_resp:
            print("ERROR: " + role_resp['errorSummary'], "Error Code ", role_resp['errorCode'])
            sys.exit(2)

        for app in role_resp:
            rolename = self.get_rolename(aws_appname, app)
            if rolename:
                return rolename

        #paginate
        while response.links['next']:
            response = requests.get(
                response.links['next']['url'],
                headers=headers,
                verify=True
            )
            role_resp = json.loads(response.text)
            # Check if this is a valid response

            if 'errorCode' in role_resp:
                print("ERROR: " + role_resp['errorSummary'], "Error Code ", role_resp['errorCode'])
                sys.exit(2)

            for app in role_resp:
                rolename = self.get_rolename(aws_appname, app)
                if rolename:
                    return rolename

        # if you made it this far something went wrong
        print("ERROR: No roles for " + aws_appname + " were returned.")
        sys.exit(3)

    @classmethod
    def get_rolename(cls, aws_appname, app):
        """ return rolename"""
        if app['label'] == aws_appname:
            print("Pick a role:")
            roles = app['_embedded']['user']['profile']['samlRoles']

            for i, role in enumerate(roles):
                print('[', i, ']:', role)
            selection = input("Selection: ")

            # make sure the choice is valid
            if int(selection) > len(roles):
                print("You selected an invalid selection")
                sys.exit(1)

            return roles[int(selection)]

        return False


    def get_app_url(self, aws_appname):
        """ return the app link json for select aws app """
        app_resp = self.get_app_links()

        for app in app_resp:
            if app['label'] == 'AWS_API':
                print(app['linkUrl'])
            if app['label'] == aws_appname:
                return app

        print("ERROR app not found:", aws_appname)
        sys.exit(2)

    def get_idp_arn(self, app_id):
        """ return the PrincipalArn based on the app instance id """
        headers = self._get_headers()
        response = requests.get(
            self._idp_entry_url + '/apps/' + app_id,
            headers=headers,
            verify=True
        )
        app_resp = json.loads(response.text)
        return app_resp['settings']['app']['identityProviderArn']

    def get_role_arn(self, link_url, aws_rolename):
        """ return the role arn for the selected role """
        # decode the saml so we can find our arns
        # https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/
        aws_roles = []
        root = et.fromstring(base64.b64decode(self.get_saml_assertion(link_url)))

        for saml2attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
            if saml2attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role':
                for saml2attributevalue in saml2attribute.iter(
                        '{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
                    aws_roles.append(saml2attributevalue.text)

        # grab the role ARNs that matches the role to assume
        for aws_role in aws_roles:
            chunks = aws_role.split(',')
            if aws_rolename in chunks[1]:
                return chunks[1]

        # if you got this far something went wrong
        print("ERROR no ARN found for", aws_rolename)
        sys.exit(2)

    def get_saml_assertion(self, app_url):
        """return the base64 SAML value object from the SAML Response"""
        if self._saml_assertion is None:
            response = requests.get(
                app_url + '/?sessionToken=' + self._session_token,
                verify=True
            )

            saml_soup = BeautifulSoup(response.text, "html.parser")
            for inputtag in saml_soup.find_all('input'):
                if inputtag.get('name') == 'SAMLResponse':
                    self._saml_assertion = inputtag.get('value')

        return self._saml_assertion
