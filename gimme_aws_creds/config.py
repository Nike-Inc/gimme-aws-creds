"""Config Class"""
import argparse
import configparser
import getpass
import os
from os.path import expanduser
import sys
from urllib.parse import urlparse
from cerberus.client import CerberusClient

class Config(object):
    """
       The Config Class gets the CLI arguments, writes out the okta config file,
       gets and returns username and password and the Okta API key.

       A lot of this code is modified from https://github.com/nimbusscale/okta_aws_login
       under the MIT license.
    """
    FILE_ROOT = expanduser("~")
    OKTA_CONFIG = FILE_ROOT + '/.okta_aws_login_config'

    def __init__(self):
        self.configure = False
        self.password = None
        self.username = None

    def get_args(self):
        """Get the CLI args"""
        parser = argparse.ArgumentParser(
            description="Gets a STS token to use for AWS CLI based "
                        "on a SAML assertion from Okta")
        parser.add_argument('--username', '-u',
                            help="The username to use when logging into Okta. The username can "
                            "also be set via the OKTA_USERNAME env variable. If not provided "
                            "you will be prompted to enter a username.")
        parser.add_argument('--configure', '-c',
                            action='store_true',
                            help="If set, will prompt user for configuration parameters "
                            " and then exit.")
        args = parser.parse_args()
        self.configure = args.configure
        self.username = args.username

    def get_config_dict(self):
        """returns the conf dict from the okta config file"""
        # Check to see if config file exists, if not complain and exit
        # If config file does exist return config dict from file
        if os.path.isfile(self.OKTA_CONFIG):
            config = configparser.ConfigParser()
            config.read(self.OKTA_CONFIG)
            return dict(config['DEFAULT'])
        else:
            print(self.OKTA_CONFIG + " is needed. Use --configure flag to "
                  "generate file.")
            sys.exit(1)

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
            print("Password must be provided")
            sys.exit(1)
        self.username = username
        self.password = password

    def get_okta_api_key(self):
        """returns the Okta API key from
        env var OKTA_API_KEY or from cerberus.
        This assumes your SDB is named Okta and
        your Vault path ends is api_key"""
        if os.environ.get("OKTA_API_KEY") is not None:
            secret = os.environ.get("OKTA_API_KEY")
        else:
            conf_dict = self.get_config_dict()
            cerberus = CerberusClient(conf_dict['cerberus_url'], self.username, self.password)
            path = cerberus.get_sdb_path('Okta')
            key = urlparse(conf_dict['idp_entry_url']).netloc
            secret = cerberus.get_secret(path + '/api_key', key)
        return secret

    def update_config_file(self):
        """
           Prompts user for config details for the okta_aws_login tool.
           Either updates exisiting config file or creates new one.
           Config Options:
                idp_entry_url = Okta URL
                write_aws_creds = Option to write creds to ~/.aws/credentials
                cred_profile = Use DEFAULT or Role as the profile in ~/.aws/credentials
                aws_appname = (optional) Okta AWS App Name
                aws_rolename =  (optional) Okta Role Name
                cerberus_url = (optional) Cerberus URL, for retrieving Okta API key
        """
        config = configparser.ConfigParser()
        # See if a config file already exists.
        # If so, use current values as defaults
        if os.path.isfile(self.OKTA_CONFIG) is True:
            config.read(self.OKTA_CONFIG)
            idp_entry_url_default = config['DEFAULT']['idp_entry_url']
            aws_appname_default = config['DEFAULT']['aws_appname']
            aws_rolename_default = config['DEFAULT']['aws_rolename']
            cerberus_url_default = config['DEFAULT']['cerberus_url']
            write_aws_creds_default = config['DEFAULT']['write_aws_creds']
            cred_profile_default = config['DEFAULT']['cred_profile']
        # otherwise use these values for defaults
        else:
            idp_entry_url_default = ""
            aws_appname_default = ""
            aws_rolename_default = ""
            cerberus_url_default = ""
            write_aws_creds_default = ""
            cred_profile_default = "role"

        # Prompt user for config details and store in config_dict
        config_dict = {}
        config_dict['idp_entry_url'] = self.get_idp_entry(idp_entry_url_default)
        config_dict['write_aws_creds'] = self.get_write_aws_creds(write_aws_creds_default)
        # if write_aws_creds is True get the profile name
        if config_dict['write_aws_creds'] is True:
            config_dict['cred_profile'] = self.get_cred_profile(cred_profile_default)
        config_dict['aws_appname'] = self.get_aws_appname(aws_appname_default)
        config_dict['aws_rolename'] = self.get_aws_rolename(aws_rolename_default)
        config_dict['cerberus_url'] = self.get_cerberus_url(cerberus_url_default)

        # Set default config
        config['DEFAULT'] = config_dict

        # write out the conf file
        with open(self.OKTA_CONFIG, 'w') as configfile:
            config.write(configfile)

    def get_idp_entry(self, default_entry):
        """ Get and validate idp_entry_url """
        print("Enter the IDP Entry URL. This is https://something.okta[preview].com")
        idp_entry_url_valid = False
        while idp_entry_url_valid is False:
            idp_entry_url = self.get_user_input("idp_entry_url", default_entry)
            # Validate that idp_entry_url is a well formed okta URL
            url_parse_results = urlparse(idp_entry_url)
            if (url_parse_results.scheme ==
                    "https" and "okta.com" or "oktapreview.com" in idp_entry_url
               ):
                idp_entry_url_valid = True
            else:
                print("idp_entry_url must be HTTPS URL for okta.com or oktapreview.com domain")
        return idp_entry_url

    def get_write_aws_creds(self, default_entry):
        """ Option to write to the ~/.aws/credentials or to stdour"""
        print("Do you want to write the temporary AWS to ~/.aws/credentials?"
              "\nIf no, the credentials will be written to stdout."
              "\nPlease answer y or n.")
        write_aws_creds = None
        while write_aws_creds != True and write_aws_creds != False:
            answer = self.get_user_input("write_aws_creds", default_entry)
            answer = answer.lower()
            if answer == 'y':
                write_aws_creds = True
            elif answer == 'n':
                write_aws_creds = False
            else:
                print("write_aws_creds must be either y or n.")
        return write_aws_creds

    def get_cred_profile(self, default_entry):
        """sets the aws credential profile name"""
        print("cred_profile defines which profile is used to store the temp AWS "
              "creds.\nIf set to 'role' then a new profile will be created "
              "matching the role name assumed by the user.\nIf set to 'default' "
              "then the temp creds will be stored in the default profile")
        cred_profile_valid = False
        cred_profile = None
        while cred_profile_valid is False:
            cred_profile = self.get_user_input("cred_profile", default_entry)
            cred_profile = cred_profile.lower()
            # validate if either role or default was entered
            if cred_profile in ["default", "role"]:
                cred_profile_valid = True
            else:
                print("cred_profile must be either default or role")
        return cred_profile

    def get_aws_appname(self, default_entry):
        """ Get Okta AWS App name """
        print("Enter the AWS Okta App Name."
              "\nThis is optional, you can select the App when you run the CLI.")
        aws_appname = self.get_user_input("aws_appname", default_entry)
        return aws_appname

    def get_aws_rolename(self, default_entry):
        """ Get the AWS Role name"""
        print("Enter the AWS role name you want credentials for."
              "\nThis is optional, you can select the role when you run the CLI.")
        aws_rolename = self.get_user_input("aws_rolename", default_entry)
        return aws_rolename

    def get_cerberus_url(self, default_entry):
        """ Get and validate cerberus url - this is optional"""
        print("If you are using Cerberus to store your Okta API Key, this is optional."
              "Enter your Cerberus URL.")
        cerberus_url = self.get_user_input("cerberus_url", default_entry)
        return cerberus_url

    @staticmethod
    def get_user_input(message, default):
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

    def clean_up(self):
        """ clean up secret stuff"""
        del self.username
        del self.password
