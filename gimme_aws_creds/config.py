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
import argparse
import configparser
import getpass
import keyring
import os
import sys
from os.path import expanduser
from urllib.parse import urlparse


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
        self.conf_profile = 'DEFAULT'

    def get_args(self):
        """Get the CLI args"""
        parser = argparse.ArgumentParser(
            description="Gets a STS token to use for AWS CLI based on a SAML assertion from Okta"
        )
        parser.add_argument(
            '--username', '-u',
            help="The username to use when logging into Okta. The username can "
            "also be set via the OKTA_USERNAME env variable. If not provided "
            "you will be prompted to enter a username."
        )
        parser.add_argument(
            '--configure', '-c',
            action='store_true',
            help="If set, will prompt user for configuration parameters and then exit."
        )
        parser.add_argument(
            '--profile', '-p',
            help='If set, the specified configuration profile will be used instead of the default.'
        )
        args = parser.parse_args()

        self.configure = args.configure
        self.username = args.username
        self.conf_profile = args.profile or 'DEFAULT'

    def get_config_dict(self):
        """returns the conf dict from the okta config file"""
        # Check to see if config file exists, if not complain and exit
        # If config file does exist return config dict from file
        if os.path.isfile(self.OKTA_CONFIG):
            config = configparser.ConfigParser()
            config.read(self.OKTA_CONFIG)

            try:
                return dict(config[self.conf_profile])
            except KeyError:
                print('Configuration profile not found!  Use the --configure flag to generate the profile.')
                sys.exit(1)
        else:
            print('Configuration file not found! Use the --configure flag to generate file.')
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
            username = self._get_user_input("Email address")
        try:
            # if the OS supports a keyring, offer to save the password
            password = keyring.get_password('gimme-aws-creds', username)
            working_keyring = True
        except:
            password = None
            working_keyring = False
        if password is not None:
            print("Using password from keyring for {}".format(username))
        else:
            # Set prompt to include the user name, since username could be set
            # via OKTA_USERNAME env and user might not remember.
            passwd_prompt = "Password for {}: ".format(username)
            password = getpass.getpass(prompt=passwd_prompt)
            if len(password) == 0:
                print("Password must be provided.")
                sys.exit(1)
            if working_keyring:
                # If the OS supports a keyring, offer to save the password
                if self._get_user_input("Do you want to save this password in the keyring?", 'y') == 'y':
                    try:
                        keyring.set_password('gimme-aws-creds', username, password)
                        print("Password for {} saved in keyring.".format(username))
                    except RuntimeError as err:
                        print("Failed to save password in keyring: ", err)
        self.username = username
        self.password = password

    def update_config_file(self):
        """
           Prompts user for config details for the okta_aws_login tool.
           Either updates existing config file or creates new one.
           Config Options:
                okta_org_url = Okta URL
                write_aws_creds = Option to write creds to ~/.aws/credentials
                cred_profile = Use DEFAULT or Role as the profile in ~/.aws/credentials
                aws_appname = (optional) Okta AWS App Name
                aws_rolename =  (optional) Okta Role Name
        """
        config = configparser.ConfigParser()
        if self.configure:
            self.conf_profile = self._get_conf_profile_name(self.conf_profile)

        defaults = {
            'okta_org_url': '',
            'aws_appname': '',
            'aws_rolename': '',
            'write_aws_creds': '',
            'cred_profile': 'role'
        }

        # See if a config file already exists.
        # If so, use current values as defaults
        if os.path.isfile(self.OKTA_CONFIG):
            config.read(self.OKTA_CONFIG)

            if self.conf_profile in config:
                profile = config[self.conf_profile]

                for default in defaults:
                    defaults[default] = profile.get(default, defaults[default])

        # Prompt user for config details and store in config_dict
        config_dict = {
            'okta_org_url': self._get_idp_entry(defaults['okta_org_url']),
            'write_aws_creds': self._get_write_aws_creds(defaults['write_aws_creds']),
            'aws_appname': self._get_aws_appname(defaults['aws_appname']),
            'aws_rolename': self._get_aws_rolename(defaults['aws_rolename']),
        }

        # If write_aws_creds is True get the profile name
        if config_dict['write_aws_creds'] is True:
            config_dict['cred_profile'] = self._get_cred_profile(defaults['cred_profile'])
        else:
            config_dict['cred_profile'] = defaults['cred_profile']

        # Set default config
        config[self.conf_profile] = config_dict

        # write out the conf file
        with open(self.OKTA_CONFIG, 'w') as configfile:
            config.write(configfile)

    def _get_idp_entry(self, default_entry):
        """ Get and validate okta_org_url """
        print("Enter the IDP Entry URL. This is https://something.okta[preview].com")
        okta_org_url_valid = False
        okta_org_url = default_entry

        while okta_org_url_valid is False:
            okta_org_url = self._get_user_input("Okta URL for your organization: ", default_entry)
            # Validate that okta_org_url is a well formed okta URL
            url_parse_results = urlparse(okta_org_url)

            if url_parse_results.scheme == "https" and "okta.com" or "oktapreview.com" in okta_org_url:
                okta_org_url_valid = True
            else:
                print("Okta organization URL must be HTTPS URL for okta.com or oktapreview.com domain")

        return okta_org_url

    def _get_write_aws_creds(self, default_entry):
        """ Option to write to the ~/.aws/credentials or to stdour"""
        print("Do you want to write the temporary AWS to ~/.aws/credentials?"
              "\nIf no, the credentials will be written to stdout."
              "\nPlease answer y or n.")
        write_aws_creds = None
        while write_aws_creds is not True and write_aws_creds is not False:
            default_entry = 'y' if default_entry is True else 'n'
            answer = self._get_user_input("Write AWS Credentials", default_entry)
            answer = answer.lower()

            if answer == 'y':
                write_aws_creds = True
            elif answer == 'n':
                write_aws_creds = False
            else:
                print("Write AWS Credentials must be either y or n.")

        return write_aws_creds

    def _get_cred_profile(self, default_entry):
        """sets the aws credential profile name"""
        print("The AWS credential profile defines which profile is used to store the temp AWS creds.\n"
              "If set to 'role' then a new profile will be created matching the role name assumed by the user.\n"
              "If set to 'default' then the temp creds will be stored in the default profile\n"
              "If set to any other value, the name of the profile will match that value.")

        cred_profile = self._get_user_input("AWS Credential Profile", default_entry)

        if cred_profile.lower() in ['default', 'role']:
            cred_profile = cred_profile.lower()

        return cred_profile

    def _get_aws_appname(self, default_entry):
        """ Get Okta AWS App name """
        print("Enter the AWS Okta App Name."
              "\nThis is optional, you can select the App when you run the CLI.")
        aws_appname = self._get_user_input("AWS App Name", default_entry)
        return aws_appname

    def _get_aws_rolename(self, default_entry):
        """ Get the AWS Role name"""
        print("Enter the AWS role name you want credentials for."
              "\nThis is optional, you can select the role when you run the CLI.")
        aws_rolename = self._get_user_input("AWS Role Name", default_entry)
        return aws_rolename

    def _get_conf_profile_name(self, default_entry):
        """Get and validate configuration profile name. [Optional]"""
        print("If you'd like to assign the Okta configuration to a specific profile\n"
              "instead of to the default profile, specify the name of the profile.\n"
              "This is optional.")
        conf_profile = self._get_user_input("Okta Configuration Profile Name", default_entry)
        return conf_profile

    @staticmethod
    def _get_user_input(message, default=None):
        """formats message to include default and then prompts user for input
        via keyboard with message. Returns user's input or if user doesn't
        enter input will return the default."""
        if default and default != '':
            prompt_message = message + " [{}]: ".format(default)
        else:
            prompt_message = message + ': '

        # print the prompt with print() rather than input() as input prompts on stderr
        print(prompt_message, end='')
        user_input = input()
        if len(user_input) == 0:
            return default
        else:
            return user_input

    def clean_up(self):
        """ clean up secret stuff"""
        del self.username
        del self.password
