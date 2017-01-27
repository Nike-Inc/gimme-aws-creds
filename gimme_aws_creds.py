#!/usr/bin/env python3
#this is a mash-up of :
# chris guthrie's example, aws security blog posts, my bad code and
# https://github.com/nimbusscale/okta_aws_login -  Joe@nimbusscale.com
#TODO in no certain order
# 1. store session id
# 2. write out to an aws config file
# 3. write a web service
# 4. use cerberus to store API key
# 5. use self.

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
        self.username = None
        self.password = None
        self.okta_api_key = None
        self.configure = False


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

    # this is modified code from https://github.com/nimbusscale/okta_aws_login
    @staticmethod
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


if __name__ == '__main__':
    GimmeAWSCreds().run()
