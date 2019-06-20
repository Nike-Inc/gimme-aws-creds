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
import os
import sys
from os.path import expanduser
from urllib.parse import urlparse

from . import version


class Config(object):
    """
       The Config Class gets the CLI arguments, writes out the okta config file,
       gets and returns username and password and the Okta API key.

       A lot of this code is modified from https://github.com/nimbusscale/okta_aws_login
       under the MIT license.
    """
    FILE_ROOT = expanduser("~")
    OKTA_CONFIG = os.environ.get("OKTA_CONFIG", os.path.join(FILE_ROOT, '.okta_aws_login_config'))

    def __init__(self):
        self.configure = False
        self.register_device = False
        self.username = None
        self.api_key = None
        self.conf_profile = 'DEFAULT'
        self.verify_ssl_certs = True
        self.app_url = None
        self.resolve = False
        self.mfa_code = None
        self.remember_device = False
        self.aws_default_duration = 3600
        self.device_token = None

        if os.environ.get("OKTA_USERNAME") is not None:
            self.username = os.environ.get("OKTA_USERNAME")

        if os.environ.get("OKTA_API_KEY") is not None:
            self.api_key = os.environ.get("OKTA_API_KEY")

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
            '--register-device',
            '--register_device',
            action='store_true',
            help='Download a device token from Okta and add it to the configuration file.'
        )
        parser.add_argument(
            '--profile', '-p',
            help='If set, the specified configuration profile will be used instead of the default.'
        )
        parser.add_argument(
            '--resolve', '-r',
            action='store_true',
            help='If set, perfom alias resolution.'
        )
        parser.add_argument(
            '--insecure', '-k',
            action='store_true',
            help='Allow connections to SSL sites without cert verification.'
        )
        parser.add_argument(
            '--mfa-code',
            help="The MFA verification code to be used with SMS or TOTP authentication methods. "
            "If not provided you will be prompted to enter an MFA verification code."
        )
        parser.add_argument(
            '--remember-device', '-m',
            action='store_true',
            help="The MFA device will be remembered by Okta service for a limited time, "
                 "otherwise, you will be prompted for it every time."
        )
        parser.add_argument(
            '--version', action='version',
            version='%(prog)s {}'.format(version),
            help='gimme-aws-creds version')
        parser.add_argument(
            '--list-profiles', action='store_true',
            help='List all the profiles under .okta_aws_login_config')
        args = parser.parse_args()

        self.configure = args.configure
        self.register_device = args.register_device
        if args.insecure is True:
            print("Warning: SSL certificate validation is disabled!")
            self.verify_ssl_certs = False
        else:
            self.verify_ssl_certs = True

        if args.list_profiles:
            if os.path.isfile(self.OKTA_CONFIG):
                with open(self.OKTA_CONFIG, 'r') as okta_config:
                    print(okta_config.read())
                    exit(0)

        if args.username is not None:
            self.username = args.username
        if args.mfa_code is not None:
            self.mfa_code = args.mfa_code
        if args.remember_device:
            self.remember_device = True
        if args.resolve is True:
            self.resolve = True
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
                print('Configuration profile not found! Use the --configure flag to generate the profile.')
                sys.exit(1)
        else:
            print('Configuration file not found! Use the --configure flag to generate file.')
            sys.exit(1)

    def update_config_file(self):
        """
           Prompts user for config details for the okta_aws_login tool.
           Either updates existing config file or creates new one.
           Config Options:
                okta_org_url = Okta URL
                gimme_creds_server = URL of the gimme-creds-server or 'internal' for local processing or 'appurl' when app url available
                client_id = OAuth Client id for the gimme-creds-server
                okta_auth_server = Server ID for the OAuth authorization server used by gimme-creds-server
                write_aws_creds = Option to write creds to ~/.aws/credentials
                cred_profile = Use DEFAULT or Role as the profile in ~/.aws/credentials
                aws_appname = (optional) Okta AWS App Name
                aws_rolename =  (optional) Okta Role ARN
                okta_username = Okta username
                aws_default_duration = Default AWS session duration (3600)
                preferred_mfa_type = Select this MFA device type automatically

        """
        config = configparser.ConfigParser()
        if self.configure:
            self.conf_profile = self._get_conf_profile_name(self.conf_profile)

        defaults = {
            'okta_org_url': '',
            'okta_auth_server': '',
            'client_id': '',
            'gimme_creds_server': 'appurl',
            'aws_appname': '',
            'aws_rolename': '',
            'write_aws_creds': '',
            'cred_profile': 'role',
            'okta_username': '',
            'app_url': '',
            'resolve_aws_alias': 'n',
            'preferred_mfa_type': '',
            'remember_device': 'n',
            'aws_default_duration': '3600',
            'device_token': ''
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
        config_dict = defaults
        config_dict['okta_org_url'] = self._get_org_url_entry(defaults['okta_org_url'])
        config_dict['gimme_creds_server'] = self._get_gimme_creds_server_entry(defaults['gimme_creds_server'])

        if config_dict['gimme_creds_server'] == 'appurl':
            config_dict['app_url'] = self._get_appurl_entry(defaults['app_url'])
        elif config_dict['gimme_creds_server'] != 'internal':
            config_dict['client_id'] = self._get_client_id_entry(defaults['client_id'])
            config_dict['okta_auth_server'] = self._get_auth_server_entry(defaults['okta_auth_server'])

        config_dict['write_aws_creds'] = self._get_write_aws_creds(defaults['write_aws_creds'])
        if config_dict['gimme_creds_server'] != 'appurl':
            config_dict['aws_appname'] = self._get_aws_appname(defaults['aws_appname'])
        config_dict['resolve_aws_alias'] = self._get_resolve_aws_alias(defaults['resolve_aws_alias'])
        config_dict['aws_rolename'] = self._get_aws_rolename(defaults['aws_rolename'])
        config_dict['okta_username'] = self._get_okta_username(defaults['okta_username'])
        config_dict['aws_default_duration'] = self._get_aws_default_duration(defaults['aws_default_duration'])
        config_dict['preferred_mfa_type'] = self._get_preferred_mfa_type(defaults['preferred_mfa_type'])
        config_dict['remember_device'] = self._get_remember_device(defaults['remember_device'])

        # If write_aws_creds is True get the profile name
        if config_dict['write_aws_creds'] is True:
            config_dict['cred_profile'] = self._get_cred_profile(
                defaults['cred_profile'])
        else:
            config_dict['cred_profile'] = defaults['cred_profile']

        self.write_config_file(config_dict)

    def write_config_file(self, config_dict):
        config = configparser.ConfigParser()
        config.read(self.OKTA_CONFIG)
        config[self.conf_profile] = config_dict

        # write out the conf file
        with open(self.OKTA_CONFIG, 'w') as configfile:
            config.write(configfile)

    def _get_org_url_entry(self, default_entry):
        """ Get and validate okta_org_url """
        print("Enter the Okta URL for your organization. This is https://something.okta[preview].com")
        okta_org_url_valid = False
        okta_org_url = default_entry

        while okta_org_url_valid is False:
            okta_org_url = self._get_user_input(
                "Okta URL for your organization", default_entry)
            # Validate that okta_org_url is a well formed okta URL
            url_parse_results = urlparse(okta_org_url)

            if url_parse_results.scheme == "https" and "okta.com" or "oktapreview.com" or "okta-emea.com" in okta_org_url:
                okta_org_url_valid = True
            else:
                print("Okta organization URL must be HTTPS URL for okta.com or oktapreview.com or okta-emea.com domain")

        self._okta_org_url = okta_org_url

        return okta_org_url

    def _get_auth_server_entry(self, default_entry):
        """ Get and validate okta_auth_server """
        print("Enter the OAuth authorization server for the gimme-creds-server. If you do not know this value, contact your Okta admin")

        okta_auth_server = self._get_user_input("Authorization server", default_entry)
        self._okta_auth_server = okta_auth_server

        return okta_auth_server

    def _get_client_id_entry(self, default_entry):
        """ Get and validate client_id """
        print("Enter the OAuth client id for the gimme-creds-server. If you do not know this value, contact your Okta admin")

        client_id = self._get_user_input("Client ID", default_entry)
        self._client_id = client_id

        return client_id

    def _get_appurl_entry(self, default_entry):
        """ Get and validate app_url """
        print("Enter the application link. This is https://something.okta[preview].com/home/amazon_aws/<app_id>/something")
        okta_org_url_valid = False
        app_url = default_entry

        while okta_org_url_valid is False:
            app_url = self._get_user_input("Application url", default_entry)
            url_parse_results = urlparse(app_url)

            if url_parse_results.scheme == "https" and "okta.com" or "oktapreview.com" or "okta-emea.com" in app_url:
                okta_org_url_valid = True
            else:
                print("Okta organization URL must be HTTPS URL for okta.com or oktapreview.com or okta-emea.com domain")

        self._app_url = app_url

        return app_url

    def _get_gimme_creds_server_entry(self, default_entry):
        """ Get gimme_creds_server """
        print("Enter the URL for the gimme-creds-server or 'internal' for handling Okta APIs locally.")
        gimme_creds_server_valid = False
        gimme_creds_server = default_entry

        while gimme_creds_server_valid is False:
            gimme_creds_server = self._get_user_input(
                "URL for gimme-creds-server", default_entry)
            if gimme_creds_server == "internal":
                gimme_creds_server_valid = True
            elif gimme_creds_server == "appurl":
                gimme_creds_server_valid = True
            else:
                url_parse_results = urlparse(gimme_creds_server)

                if url_parse_results.scheme == "https":
                    gimme_creds_server_valid = True
                else:
                    print("The gimme-creds-server must be a HTTPS URL")

        return gimme_creds_server

    def _get_write_aws_creds(self, default_entry):
        """ Option to write to the ~/.aws/credentials or to stdour"""
        print("Do you want to write the temporary AWS to ~/.aws/credentials?"
              "\nIf no, the credentials will be written to stdout."
              "\nPlease answer y or n.")
        write_aws_creds = None
        while write_aws_creds is not True and write_aws_creds is not False:
            default_entry = 'y' if default_entry is True else 'n'
            answer = self._get_user_input(
                "Write AWS Credentials", default_entry)
            answer = answer.lower()

            if answer == 'y':
                write_aws_creds = True
            elif answer == 'n':
                write_aws_creds = False
            else:
                print("Write AWS Credentials must be either y or n.")

        return write_aws_creds

    def _get_resolve_aws_alias(self, default_entry):
        """ Option to resolve account id to alias """
        print("Do you want to resolve aws account id to aws alias ?"
              "\nPlease answer y or n.")
        resolve_aws_alias = None
        while resolve_aws_alias is not True and resolve_aws_alias is not False:
            default_entry = 'y' if default_entry is True else 'n'
            answer = self._get_user_input(
                "Resolve AWS alias", default_entry)
            answer = answer.lower()

            if answer == 'y':
                resolve_aws_alias = True
            elif answer == 'n':
                resolve_aws_alias = False
            else:
                print("Resolve AWS alias must be either y or n.")

        return resolve_aws_alias


    def _get_cred_profile(self, default_entry):
        """sets the aws credential profile name"""
        print("The AWS credential profile defines which profile is used to store the temp AWS creds.\n"
              "If set to 'role' then a new profile will be created matching the role name assumed by the user.\n"
              "If set to 'default' then the temp creds will be stored in the default profile\n"
              "If set to any other value, the name of the profile will match that value.")

        cred_profile = self._get_user_input(
            "AWS Credential Profile", default_entry)

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
        """ Get the AWS Role ARN"""
        print("Enter the ARN for the AWS role you want credentials for. 'all' will retrieve all roles."
              "\nThis is optional, you can select the role when you run the CLI.")
        aws_rolename = self._get_user_input("AWS Role ARN", default_entry)
        return aws_rolename

    def _get_conf_profile_name(self, default_entry):
        """Get and validate configuration profile name. [Optional]"""
        print("If you'd like to assign the Okta configuration to a specific profile\n"
              "instead of to the default profile, specify the name of the profile.\n"
              "This is optional.")
        conf_profile = self._get_user_input(
            "Okta Configuration Profile Name", default_entry)
        return conf_profile

    def _get_okta_username(self, default_entry):
        """Get and validate okta username. [Optional]"""
        print("If you'd like to set your okta username in the config file, specify the username\n."
              "This is optional.")
        okta_username = self._get_user_input(
            "Okta User Name", default_entry)
        return okta_username

    def _get_aws_default_duration(self, default_entry):
        """Get and validate the aws default session duration. [Optional]"""
        print("If you'd like to set the default session duration, specify it (in seconds).\n"
              "This is optional.")
        aws_default_duration = self._get_user_input(
            "AWS Default Session Duration", default_entry)
        return aws_default_duration

    def _get_preferred_mfa_type(self, default_entry):
        """Get the user's preferred MFA device [Optional]"""
        print("If you'd like to set a preferred device type to use for MFA, enter it here.\n"
              "This is optional. valid devices types:[sms, call, push, token, token:software:totp]")
        okta_username = self._get_user_input(
            "Preferred MFA Device Type", default_entry)
        return okta_username

    def _get_remember_device(self, default_entry):
        """Option to remember the MFA device"""
        print("Do you want the MFA device be remembered?\n"
              "Please answer y or n.")
        remember_device = None
        while remember_device is not True and remember_device is not False:
            default_entry = 'y' if default_entry is True else 'n'
            answer = self._get_user_input(
                "Remember device", default_entry)
            answer = answer.lower()

            if answer == 'y':
                remember_device = True
            elif answer == 'n':
                remember_device = False
            else:
                print("Remember the MFA device must be either y or n.")

        return remember_device

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
        del self.api_key
