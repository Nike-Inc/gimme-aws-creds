#!/usr/bin/env python3

import boto3
import json
import os
import re
import requests
import sys

from gimme_aws_creds.config import Config
from gimme_aws_creds.okta import OktaClient

class GimmeAWSCreds(object):
    AWS_CONFIG = FILE_ROOT + '/.aws/credentials'

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

    def get_sts_creds(self,assertion,duration=3600):
        """ using the assertion and arns return aws sts creds """
        client = boto3.client('sts')
        response = client.assume_role_with_saml(
           RoleArn=self.role_arn,
           PrincipalArn=self.idp_arn,
           SAMLAssertion=assertion,
           DurationSeconds=duration)
        return response['Credentials']

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
        if not conf_dict['aws_rolename']:
            # get available roles for the AWS app
            self.aws_rolename = okta.get_role(resp,self.aws_appname)
        else:
            self.aws_rolename = conf_dict['aws_rolename']

        # get the applinks available to the user
        app_url = okta.get_app_url(resp,self.aws_appname)
        # Get the the identityProviderArn from the aws app
        self.idp_arn = okta.get_idp_arn(app_url['appInstanceId'])
        # Get the role ARNs
        self.role_arn = okta.get_role_arn(app_url['linkUrl'],resp['sessionToken'],self.aws_rolename)
        # get a new token for aws_creds
        login_resp = okta.get_login_response(config.username, config.password)
        resp2 = requests.get(app_url['linkUrl'] + '/?sessionToken=' + login_resp['sessionToken'], verify=True)
        #session = requests.session()
        assertion = okta.get_saml_assertion(resp2)
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

        config.clean_up()

if __name__ == '__main__':
    GimmeAWSCreds().run()
