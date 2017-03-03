#!/usr/bin/env python3
# TODO in no certain order
# 1. add MFA for Okta
# 2. write out to an aws config file
# 3. write a web service
# 4. store session id


import base64
import boto3


import json
import os
import re
import requests
import sys
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

#from os.path import expanduser
#from urllib.parse import urlparse, urlunparse
from gimme_aws_creds.config import Config
from gimme_aws_creds.okta import OktaClient

class GimmeAWSCreds(object):

    def __init__(self):
        self.aws_appname = None
        self.aws_rolename = None
        self.cerberus_url = None
        self.idp_entry_url = None
        self.idp_arn = None
        self.okta_api_key = None
        self.password = None
        self.role_arn = None
        self.username = None

    def get_headers(self):
        headers = {'Accept' : 'application/json',
                   'Content-Type' : 'application/json',
                   'Authorization' : 'SSWS ' + self.okta_api_key}
        return headers


    #  this is modified code from https://github.com/nimbusscale/okta_aws_login
    def write_aws_creds(self, profile, access_key, secret_key, token):
        """ Writes the AWS STS token into the AWS credential file"""
        # Check to see if the aws creds path exists, if not create it
        creds_dir = os.path.dirname(self.AWS_CONFIG)
        if os.path.exists(creds_dir) == False:
           os.makedirs(creds_dir)
        config = configparser.RawConfigParser()
        # Read in the existing config file if it exists
        if os.path.isfile(self.AWS_CONFIG):
            config.read(self.AWS_CONFIG)
        # Put the credentials into a saml specific section instead of clobbering
        # the default credentials
        if not config.has_section(profile):
            config.add_section(profile)
        config.set(profile, 'aws_access_key_id', access_key)
        config.set(profile, 'aws_secret_access_key', secret_key)
        config.set(profile, 'aws_session_token', token)
        # Write the updated config file
        with open(self.AWS_CONFIG, 'w+') as configfile:
            config.write(configfile)



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


    def get_role(self,login_resp):
        """ gets a list of available roles and
        ask the user to select the app they want
        to assume and returns the selection"""
        # get available roles for the AWS app
        headers = self.get_headers()
        user_id = login_resp['_embedded']['user']['id']
        response = requests.get(self.idp_entry_url + '/apps/?filter=user.id+eq+\"' +
            user_id + '\"&expand=user/' + user_id,headers=headers, verify=True)
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
        config = Config()
        config.get_args()
        #Create/Update config when configure arg set
        if config.configure == True:
            config.update_config_file()
            sys.exit()

        # get the config dict
        conf_dict = config.get_config_dict()

        config.get_user_creds()

        self.idp_entry_url = conf_dict['idp_entry_url'] + '/api/v1'
        # this assumes you are using a cerberus backend
        # to store your okta api key, and the key name
        # is the hostname for your okta env
        # otherwise set OKTA_API_KEY env variable
        if conf_dict['cerberus_url'] :
            self.cerberus_url = conf_dict['cerberus_url']
        api_key = config.get_okta_api_key()

        okta = OktaClient(api_key, self.idp_entry_url)
        resp = okta.get_login_response(config.username, config.password)
        session = requests.session()

        # check to see if appname and rolename are set
        # in the config, if not give user a selection to pick from
        if not conf_dict['aws_appname']:
            self.aws_appname = okta.get_app(resp)
        else:
            self.aws_appname = conf_dict['aws_appname']
        sys.exit()
        if not conf_dict['aws_rolename']:
            # get available roles for the AWS app
            self.aws_rolename = self.get_role(resp)
        else:
            self.aws_rolename = conf_dict['aws_rolename']

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
        if conf_dict['write_aws_creds']:
            print('writing to ', self.AWS_CONFIG)
            # set the profile name
            if conf_dict['cred_profile'] == 'default':
                profile_name = 'default'
            elif conf_dict['cred_profile'] == 'role':
                profile_name = self.aws_rolename
            # write out the AWS Config file
            self.write_aws_creds(profile_name,
                                 aws_creds['AccessKeyId'],
                                 aws_creds['SecretAccessKey'],
                                 aws_creds['SessionToken'] )
        else:
            # print out creds
            print("export AWS_ACCESS_KEY_ID=" + aws_creds['AccessKeyId'])
            print("export AWS_SECRET_ACCESS_KEY=" + aws_creds['SecretAccessKey'])
            print("export AWS_SESSION_TOKEN=" + aws_creds['SessionToken'])

        self.clean_up()

if __name__ == '__main__':
    GimmeAWSCreds().run()
