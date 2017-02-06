#!/usr/bin/env python3
# TODO in no certain order
# 1. add MFA for Okta
# 2. write out to an aws config file
# 3. write a web service
# 4. store session id

import argparse
import base64
import boto3
import configparser
import getpass
import json
import os
import re
import requests
import sys
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from CerberusMiniClient import CerberusMiniClient
from os.path import expanduser
from urllib.parse import urlparse, urlunparse

class GimmeAWSCreds(object):
    FILE_ROOT = expanduser("~")
    OKTA_CONFIG = FILE_ROOT + '/.okta_aws_login_config'

    def __init__(self):
        self.aws_appname = None
        self.aws_rolename = None
        self.configure = False
        self.idp_entry_url = None
        self.idp_arn = None
        self.okta_api_key = None
        self.password = None
        self.role_arn = None
        self.username = None

    def get_headers(self):
        headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json', 'Authorization' : 'SSWS ' + self.okta_api_key}
        return headers

    def get_args(self):
        parser = argparse.ArgumentParser(
            description = "Gets a STS token to use for AWS CLI based "
                           "on a SAML assertion from Okta")
        parser.add_argument('--username', '-u',
            help = "The username to use when logging into Okta. The username can "
                   "also be set via the OKTA_USERNAME env variable. If not provided "
                   "you will be prompted to enter a username.")
        parser.add_argument('--configure', '-c',
            action = 'store_true',
            help = "If set, will prompt user for configuration parameters "
                    " and then exit.")
        args = parser.parse_args()
        self.configure = args.configure
        self.username = args.username


    # this is modified code from https://github.com/nimbusscale/okta_aws_login
    def update_config_file(self):
        """Prompts user for config details for the okta_aws_login tool.
        Either updates exisiting config file or creates new one."""
        config = configparser.ConfigParser()
        # See if a config file already exists.
        # If so, use current values as defaults
        if os.path.isfile(self.OKTA_CONFIG) == True:
            config.read(self.OKTA_CONFIG)
            idp_entry_url_default = config['DEFAULT']['idp_entry_url']
            aws_appname_default = config['DEFAULT']['aws_appname']
            aws_rolename_default = config['DEFAULT']['aws_rolename']
        # otherwise use these values for defaults
        else:
            idp_entry_url_default = ""
            aws_appname_default = ""
            aws_rolename_default = ""
        # Prompt user for config details and store in config_dict
        config_dict = {}
        # Get and validate idp_entry_url
        print("Enter the IDP Entry URL. This is https://something.okta[preview].com")
        idp_entry_url_valid = False
        while idp_entry_url_valid == False:
            idp_entry_url =  self.get_user_input("idp_entry_url",idp_entry_url_default)
            # Validate that idp_entry_url is a well formed okta URL
            url_parse_results = urlparse(idp_entry_url)
            if (url_parse_results.scheme == "https" and
                                         "okta.com" or "oktapreview.com" in idp_entry_url):
                idp_entry_url_valid = True
            else:
                print("idp_entry_url must be HTTPS URL for okta.com or oktapreview.com domain")
        config_dict['idp_entry_url'] = idp_entry_url
        # Get Okta AWS App name
        print('Enter the AWS Okta App Name '
               "This is optional, you can select the App when you run the CLI.")
        aws_appname = self.get_user_input("aws_appname",aws_appname_default)
        config_dict['aws_appname'] = aws_appname
        # Get the AWS Role name - this is optional to make the program less interactive
        print("Enter the AWS role name you want credentials for."
               "This is optional, you can select the role when you run the CLI.")
        aws_rolename = self.get_user_input("aws_rolename",aws_rolename_default)
        config_dict['aws_rolename'] = aws_rolename
        # Set default config
        config['DEFAULT'] = config_dict
        with open(self.OKTA_CONFIG, 'w') as configfile:
            config.write(configfile)

    @staticmethod
    # this is modified code from https://github.com/nimbusscale/okta_aws_login
    def get_user_input(message,default):
        """formats message to include default and then prompts user for input
        via keyboard with message. Returns user's input or if user doesn't
        enter input will return the default."""
        message_with_default = message + " [{}]: ".format(default)
        user_input = input(message_with_default)
        print("")
        if len(user_input) == 0:
            return default
        else:
            return user_input

    #  this is modified code from https://github.com/nimbusscale/okta_aws_login
    def get_user_creds(self):
        """Get's creds for Okta login from the user."""
        # Check to see if the username arg has been set, if so use that
        if self.username is not None:
            username = self.username
        # Next check to see if the OKTA_USERNAME env var is set
        elif os.environ.get("OKTA_USERNAME") is not None:
            username = os.environ.get("OKTA_USERNAME")
        # Otherwise just ask the user
        else:
            username = input("Email address: ")
        # Set prompt to include the user name, since username could be set
        # via OKTA_USERNAME env and user might not remember.
        passwd_prompt = "Password for {}: ".format(username)
        password = getpass.getpass(prompt=passwd_prompt)
        if len(password) == 0:
            print( "Password must be provided")
            sys.exit(1)
        self.username = username
        self.password = password

    def set_okta_api_key(self,key):
        """returns the Okta API key from cerberus.
        This assumes your SDB is named Okta and
        your Vault path ends is api_key"""
        cerberus = CerberusMiniClient(self.username,self.password)
        path = cerberus.get_sdb_path('Okta')
        secret = cerberus.get_secret(path + '/api_key', key)
        self.okta_api_key = secret

    def get_login_response(self):
        """ gets the login response from Okta and returns the json response"""
        headers = self.get_headers()
        response = requests.post(self.idp_entry_url + '/authn',
                                 json={'username': self.username, 'password': self.password},
                                 headers=headers)
        if response.status_code != 200:
            print("ERROR: " + response['errors'][0]['message'])
            sys.exit(2)
        response_json = json.loads(response.text)
        return response_json

    def get_app_links(self,login_resp):
        """ return appLinks obejct for the user """
        headers = self.get_headers()
        user_id = login_resp['_embedded']['user']['id']
        response = requests.get(self.idp_entry_url + '/users/' + user_id + '/appLinks',
              headers=headers, verify=True)
        app_resp = json.loads(response.text)
        if 'errorCode' in app_resp:
            print("ERROR: " + app_resp['errorSummary'], "Error Code ", app_resp['errorCode'])
            sys.exit(2)
        return app_resp

    def get_app(self,login_resp):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection"""
        app_resp = self.get_app_links(login_resp)
        print ("Pick an app:")
        # print out the apps and let the user select
        for i, app in enumerate(app_resp):
            print ('[',i,']', app["label"])
        selection = input("Selection: ")
        # make sure the choice is valid
        if int(selection) > len(app_resp):
            print ("You selected an invalid selection")
            sys.exit(1)
        return app_resp[int(selection)]["label"]

    def get_role(self,login_resp):
        """ gets a list of available roles and
        ask the user to select the app they want
        to assume and returns the selection"""
        # get available roles for the AWS app
        headers = self.get_headers()
        user_id = login_resp['_embedded']['user']['id']
        response = requests.get(self.idp_entry_url + '/apps/?filter=user.id+eq+\"' +
            user_id + '\"&expand=user/' + user_id,headers=headers, verify=True)
        print(response.text)
        role_resp = json.loads(response.text)
        # Check if this is a valid response
        if 'errorCode' in role_resp:
            print("ERROR: " + role_resp['errorSummary'], "Error Code ", role_resp['errorCode'])
            sys.exit(2)
        # print out roles for the app and let the uesr select
        for app in role_resp:
            if app['label'] == self.aws_appname:
                print ("Pick a role:")
                roles = app['_embedded']['user']['profile']['samlRoles']
                for i, role in enumerate(roles):
                    print ('[',i,']:', role)
                selection = input("Selection: ")
                # make sure the choice is valid
                if int(selection) > len(roles):
                    print ("You selected an invalid selection")
                    sys.exit(1)
                return roles[int(selection)]

    def get_app_url(self,login_resp):
        """ return the app link json for select aws app """
        app_resp = self.get_app_links(login_resp)
        for app in app_resp:
            #print(app['label'])
            if(app['label'] == 'AWS_API'):
                print(app['linkUrl'])
            if app['label'] == self.aws_appname:
                return app

        print("ERROR app not found:", self.aws_appname)
        sys.exit(2)

    def set_idp_arn(self,app_id):
        """ return the PrincipalArn based on the app instance id """
        headers = self.get_headers()
        response = requests.get(self.idp_entry_url + '/apps/' + app_id ,headers=headers, verify=True)
        app_resp = json.loads(response.text)
        self.idp_arn = app_resp['settings']['app']['identityProviderArn']

    def set_role_arn(self,link_url,token):
        """ return the role arn for the selected role """
        headers = self.get_headers()
        saml_resp = requests.get(link_url + '/?onetimetoken=' + token, headers=headers, verify=True)
        saml_value = self.get_saml_assertion(saml_resp)
        # decode the saml so we can find our arns
        # https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/
        aws_roles = []
        root = ET.fromstring(base64.b64decode(saml_value))
        #print(BeautifulSoup(saml_decoded, "lxml").prettify())
        for saml2attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
            if (saml2attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role'):
                for saml2attributevalue in saml2attribute.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
                    aws_roles.append(saml2attributevalue.text)
        # grab the role ARNs that matches the role to assume
        role_arn = ''
        for aws_role in aws_roles:
            chunks = aws_role.split(',')
            if self.aws_rolename in chunks[1]:
                self.role_arn = chunks[1]

    @staticmethod
    def get_saml_assertion(response):
        """return the base64 SAML value object from the SAML Response"""
        saml_soup = BeautifulSoup(response.text, "html.parser")
        #print("SOUP", saml_soup)
        for inputtag in saml_soup.find_all('input'):
            if (inputtag.get('name') == 'SAMLResponse'):
                return inputtag.get('value')

    def get_sts_creds(self,assertion,duration=3600):
        """ using the assertion and arns return aws sts creds """
        client = boto3.client('sts')
        response = client.assume_role_with_saml(
           RoleArn=self.role_arn,
           PrincipalArn=self.idp_arn,
           SAMLAssertion=assertion,
           DurationSeconds=duration)
        return response['Credentials']

    def clean_up(self):
        """ clean up secret stuff"""
        del self.username
        del self.password
        del self.okta_api_key


    def run(self):
        """ let's do this """
        self.get_args()
        #Create/Update config when configure arg set
        if self.configure == True:
            self.update_config_file()
            sys.exit()
        # Check to see if config file exists, if not complain and exit
        # If config file does exist create config dict from file
        if os.path.isfile(self.OKTA_CONFIG):
            config = configparser.ConfigParser()
            config.read(self.OKTA_CONFIG)
            conf_dict = dict(config['DEFAULT'])
        else:
            print(self.OKTA_CONFIG + " is needed. Use --configure flag to "
                    "generate file.")
            sys.exit(1)

        self.get_user_creds()
        self.idp_entry_url = conf_dict['idp_entry_url'] + '/api/v1'
        # this assumes you are using a cerberus backend
        # to store your okta api key, and the key name
        # is the hostname for your okta env
        cerberus_key = urlparse(self.idp_entry_url).netloc
        self.set_okta_api_key(cerberus_key)

        resp = self.get_login_response()
        session = requests.session()

        # check to see if appname and rolename are set
        # in the config, if not give user a selection to pick from
        if not conf_dict['aws_appname']:
            self.aws_appname = self.get_app(resp)
        else:
            self.aws_appname = conf_dict['aws_appname']
        if not conf_dict['aws_rolename']:
            # get available roles for the AWS app
            self.aws_rolename = self.get_role(resp)
        else:
            self.aws_rolename = conf_dict['aws_rolename']

        sys.exit(0)

        # get the applinks available to the user
        app_url = self.get_app_url(resp)
        # Get the the identityProviderArn from the aws app
        self.set_idp_arn(app_url['appInstanceId'])
        # Get the role ARNs
        self.set_role_arn(app_url['linkUrl'],resp['sessionToken'])
        # get a new token for aws_creds
        login_resp = self.get_login_response()
        resp2 = requests.get(app_url['linkUrl'] + '/?sessionToken=' + login_resp['sessionToken'], verify=True)
        #session = requests.session()
        assertion = self.get_saml_assertion(resp2)
        aws_creds = self.get_sts_creds(assertion)
        # print out creds
        print("export AWS_ACCESS_KEY_ID=" + aws_creds['AccessKeyId'])
        print("export AWS_SECRET_ACCESS_KEY=" + aws_creds['SecretAccessKey'])

        self.clean_up()

if __name__ == '__main__':
    GimmeAWSCreds().run()
