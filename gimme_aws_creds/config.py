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
from urllib.parse import urlparse

from . import errors, ui, version


class Config(object):
    """
       The Config Class gets the CLI arguments, writes out the okta config file,
       gets and returns username and password and the Okta API key.

       A lot of this code is modified from https://github.com/nimbusscale/okta_aws_login
       under the MIT license.
    """

    def __init__(self, gac_ui, create_config=True):
        """
        :type gac_ui: ui.UserInterface
        """
        self.ui = gac_ui
        self.FILE_ROOT = self.ui.HOME
        self.OKTA_CONFIG = self.ui.environ.get(
            'OKTA_CONFIG',
            os.path.join(self.FILE_ROOT, '.okta_aws_login_config')
        )
        self.action_register_device = False
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
        self.action_configure = False
        self.action_list_profiles = False
        self.action_list_roles = False
        self.action_store_json_creds = False
        self.action_setup_fido_authenticator = False
        self.action_output_format = False
        self.output_format = 'export'
        self.roles = []

        if self.ui.environ.get("OKTA_USERNAME") is not None:
            self.username = self.ui.environ.get("OKTA_USERNAME")

        if self.ui.environ.get("OKTA_API_KEY") is not None:
            self.api_key = self.ui.environ.get("OKTA_API_KEY")

        if create_config and not os.path.isfile(self.OKTA_CONFIG):
            self.ui.notify('No gimme-aws-creds configuration file found, starting first-time configuration...')
            self.update_config_file()

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
            '--action-configure', '--configure', '-c',
            action='store_true',
            help="If set, will prompt user for configuration parameters and then exit."
        )
        parser.add_argument(
            '--action-register-device',
            '--register-device',
            '--register_device',
            action='store_true',
            help='Download a device token from Okta and add it to the configuration file.'
        )
        parser.add_argument(
            '--output-format', '-o',
            choices=['export', 'json'],
            help='Output credentials as either list of shell exports or lines of structured JSON.'
        )
        parser.add_argument(
            '--profile', '-p',
            help='If set, the specified configuration profile will be used instead of the default.'
        )
        parser.add_argument(
            '--roles',
            help='If set, the specified role will be used instead of the aws_rolename in the profile, '
                 'can be specified as a comma separated list, '
                 'can be regex in format /<pattern>/. '
                 'for example: arn:aws:iam::123456789012:role/Admin,/:210987654321:/ '
                 'would match both account 123456789012 by ARN and 210987654321 by regexp'
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
                 "If not provided you will be prompted to enter an MFA verification code. "
                 "Can be read from OKTA_MFA_CODE environment variable"
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
            '--action-list-profiles', '--list-profiles', action='store_true',
            help='List all the profiles under .okta_aws_login_config')
        parser.add_argument(
            '--action-list-roles', action='store_true',
            help='List all the roles in the selected profile')
        parser.add_argument(
            '--action-store-json-creds', action='store_true',
            help='Read credentials from stdin (in json format) and store them in ~/.aws/credentials file')
        parser.add_argument(
            '--action-setup-fido-authenticator', action='store_true',
            help='Sets up a new FIDO WebAuthn authenticator in Okta'
        )
        args = parser.parse_args(self.ui.args)

        self.action_configure = args.action_configure
        self.action_list_profiles = args.action_list_profiles
        self.action_list_roles = args.action_list_roles
        self.action_store_json_creds = args.action_store_json_creds
        self.action_register_device = args.action_register_device
        self.action_setup_fido_authenticator = args.action_setup_fido_authenticator

        if args.insecure is True:
            ui.default.warning("Warning: SSL certificate validation is disabled!")
            self.verify_ssl_certs = False
        else:
            self.verify_ssl_certs = True

        if args.username is not None:
            self.username = args.username
        if args.mfa_code is not None:
            self.mfa_code = args.mfa_code
        if args.remember_device:
            self.remember_device = True
        if args.resolve is True:
            self.resolve = True
        if args.output_format is not None:
            self.action_output_format = args.output_format
            self.output_format = args.output_format
        if args.roles is not None:
            self.roles = [role.strip() for role in args.roles.split(',') if role.strip()]
        self.conf_profile = args.profile or 'DEFAULT'

    def _handle_config(self, config, profile_config, include_inherits = True):
        if "inherits" in profile_config.keys() and include_inherits:
            self.ui.message("Using inherited config: " + profile_config["inherits"])
            if profile_config["inherits"] not in config:
                raise errors.GimmeAWSCredsError(self.conf_profile + " inherits from " + profile_config["inherits"] + ", but could not find " + profile_config["inherits"])
            combined_config = {
                **self._handle_config(config, dict(config[profile_config["inherits"]])),
                **profile_config,
            }
            del combined_config["inherits"]
            return combined_config
        else:
            return profile_config

    def get_config_dict(self, include_inherits = True):
        """returns the conf dict from the okta config file"""
        # Check to see if config file exists, if not complain and exit
        # If config file does exist return config dict from file
        if os.path.isfile(self.OKTA_CONFIG):
            config = configparser.ConfigParser()
            config.read(self.OKTA_CONFIG)

            try:
                profile_config = dict(config[self.conf_profile])
                self.fail_if_profile_not_found(profile_config, self.conf_profile, config.default_section)
                return self._handle_config(config, profile_config, include_inherits)
            except KeyError:
                if self.action_configure:
                    return {}
                raise errors.GimmeAWSCredsError(
                    'Configuration profile not found! Use the --action-configure flag to generate the profile.')
        raise errors.GimmeAWSCredsError('Configuration file not found! Use the --action-configure flag to generate file.')

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
                cred_profile = Use DEFAULT or Role-based name as the profile in ~/.aws/credentials
                aws_appname = (optional) Okta AWS App Name
                aws_rolename =  (optional) Okta Role ARN
                okta_username = Okta username
                aws_default_duration = Default AWS session duration (3600)
                preferred_mfa_type = Select this MFA device type automatically
                include_path - (optional) includes that full role path to the role name for profile

        """
        config = configparser.ConfigParser()
        if self.action_configure:
            self.conf_profile = self._get_conf_profile_name(self.conf_profile)

        defaults = {
            'okta_org_url': '',
            'okta_auth_server': '',
            'client_id': '',
            'gimme_creds_server': 'appurl',
            'aws_appname': '',
            'aws_rolename': ','.join(self.roles),
            'write_aws_creds': '',
            'cred_profile': 'role',
            'okta_username': '',
            'app_url': '',
            'resolve_aws_alias': 'n',
            'include_path': 'n',
            'preferred_mfa_type': '',
            'remember_device': 'n',
            'aws_default_duration': '3600',
            'device_token': '',
            'output_format': 'export',
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
        config_dict['include_path'] = self._get_include_path(defaults['include_path'])
        config_dict['aws_rolename'] = self._get_aws_rolename(defaults['aws_rolename'])
        config_dict['okta_username'] = self._get_okta_username(defaults['okta_username'])
        config_dict['aws_default_duration'] = self._get_aws_default_duration(defaults['aws_default_duration'])
        config_dict['preferred_mfa_type'] = self._get_preferred_mfa_type(defaults['preferred_mfa_type'])
        config_dict['remember_device'] = self._get_remember_device(defaults['remember_device'])
        config_dict["output_format"] = ''
        if not config_dict["write_aws_creds"]:
            config_dict['output_format'] = self._get_output_format(defaults['output_format'])

        # If write_aws_creds is True get the profile name
        if config_dict['write_aws_creds'] is True:
            config_dict['cred_profile'] = self._get_cred_profile(defaults['cred_profile'])
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
        ui.default.info("Enter the Okta URL for your organization. This is https://something.okta[preview].com")
        okta_org_url_valid = False
        okta_org_url = default_entry

        while okta_org_url_valid is False:
            okta_org_url = self._get_user_input("Okta URL for your organization", default_entry).strip('/')
            # Validate that okta_org_url is a well formed okta URL
            url_parse_results = urlparse(okta_org_url)

            if url_parse_results.scheme == "https" and "okta.com" or "oktapreview.com" or "okta-emea.com" in okta_org_url:
                okta_org_url_valid = True
            else:
                ui.default.error(
                    "Okta organization URL must be HTTPS URL for okta.com or oktapreview.com or okta-emea.com domain")

        self._okta_org_url = okta_org_url

        return okta_org_url

    def _get_auth_server_entry(self, default_entry):
        """ Get and validate okta_auth_server """
        ui.default.message(
            "Enter the OAuth authorization server for the gimme-creds-server. If you do not know this value, contact your Okta admin")

        okta_auth_server = self._get_user_input("Authorization server", default_entry)
        self._okta_auth_server = okta_auth_server

        return okta_auth_server

    def _get_client_id_entry(self, default_entry):
        """ Get and validate client_id """
        ui.default.message(
            "Enter the OAuth client id for the gimme-creds-server. If you do not know this value, contact your Okta admin")

        client_id = self._get_user_input("Client ID", default_entry)
        self._client_id = client_id

        return client_id

    def _get_appurl_entry(self, default_entry):
        """ Get and validate app_url """
        ui.default.message(
            "Enter the application link. This is https://something.okta[preview].com/home/amazon_aws/<app_id>/something")
        okta_org_url_valid = False
        app_url = default_entry

        while okta_org_url_valid is False:
            app_url = self._get_user_input("Application url", default_entry)
            url_parse_results = urlparse(app_url)

            if url_parse_results.scheme == "https" and "okta.com" or "oktapreview.com" or "okta-emea.com" in app_url:
                okta_org_url_valid = True
            else:
                ui.default.warning(
                    "Okta organization URL must be HTTPS URL for okta.com or oktapreview.com or okta-emea.com domain")

        self._app_url = app_url

        return app_url

    def _get_gimme_creds_server_entry(self, default_entry):
        """ Get gimme_creds_server """
        ui.default.message("Enter the URL for the gimme-creds-server or 'internal' for handling Okta APIs locally.")
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
                    ui.default.warning("The gimme-creds-server must be a HTTPS URL")

        return gimme_creds_server

    def _get_write_aws_creds(self, default_entry):
        """ Option to write to the ~/.aws/credentials or to stdour"""
        ui.default.message(
            "Do you want to write the temporary AWS to ~/.aws/credentials?"
            "\nIf no, the credentials will be written to stdout."
            "\nPlease answer y or n.")

        while True:
            try:
                return self._get_user_input_yes_no("Write AWS Credentials", default_entry)
            except ValueError:
                ui.default.warning("Write AWS Credentials must be either y or n.")

    def _get_include_path(self, default_entry):
        """ Option to include path from rolename """

        ui.default.message(
            "Do you want to include full role path to the role name in AWS credential profile name?"
            "\nPlease answer y or n.")

        while True:
            try:
                return self._get_user_input_yes_no("Include Path", default_entry)
            except ValueError:
                ui.default.warning("Include Path must be either y or n.")

    def _get_resolve_aws_alias(self, default_entry):
        """ Option to resolve account id to alias """
        ui.default.message(
            "Do you want to resolve aws account id to aws alias ?"
            "\nPlease answer y or n.")
        while True:
            try:
                return self._get_user_input_yes_no("Resolve AWS alias", default_entry)
            except ValueError:
                ui.default.warning("Resolve AWS alias must be either y or n.")

    def _get_cred_profile(self, default_entry):
        """sets the aws credential profile name"""
        ui.default.message(
            "The AWS credential profile defines which profile is used to store the temp AWS creds.\n"
            "If set to 'role' then a new profile will be created matching the role name assumed by the user.\n"
            "If set to 'acc-role' then a new profile will be created matching the role name assumed by the user, but prefixed with account number to avoid collisions.\n"
            "If set to 'default' then the temp creds will be stored in the default profile\n"
            "If set to any other value, the name of the profile will match that value."
        )

        cred_profile = self._get_user_input(
            "AWS Credential Profile", default_entry)

        if cred_profile.lower() in ['default', 'role', 'acc-role']:
            cred_profile = cred_profile.lower()

        return cred_profile

    def _get_aws_appname(self, default_entry):
        """ Get Okta AWS App name """
        ui.default.message(
            "Enter the AWS Okta App Name."
            "\nThis is optional, you can select the App when you run the CLI.")
        aws_appname = self._get_user_input("AWS App Name", default_entry)
        return aws_appname

    def _get_aws_rolename(self, default_entry):
        """ Get the AWS Role ARN"""
        ui.default.message(
            "Enter the ARN for the AWS role you want credentials for. 'all' will retrieve all roles."
            "\nThis is optional, you can select the role when you run the CLI.")
        aws_rolename = self._get_user_input("AWS Role ARN", default_entry)
        return aws_rolename

    def _get_conf_profile_name(self, default_entry):
        """Get and validate configuration profile name. [Optional]"""
        ui.default.message(
            "If you'd like to assign the Okta configuration to a specific profile\n"
            "instead of to the default profile, specify the name of the profile.\n"
            "This is optional.")
        conf_profile = self._get_user_input(
            "Okta Configuration Profile Name", default_entry)
        return conf_profile

    def _get_okta_username(self, default_entry):
        """Get and validate okta username. [Optional]"""
        ui.default.message(
            "If you'd like to set your okta username in the config file, specify the username\n."
            "This is optional.")
        okta_username = self._get_user_input(
            "Okta User Name", default_entry)
        return okta_username

    def _get_aws_default_duration(self, default_entry):
        """Get and validate the aws default session duration. [Optional]"""
        ui.default.message(
            "If you'd like to set the default session duration, specify it (in seconds).\n"
            "This is optional.")
        aws_default_duration = self._get_user_input(
            "AWS Default Session Duration", default_entry)
        return aws_default_duration

    def _get_preferred_mfa_type(self, default_entry):
        """Get the user's preferred MFA device [Optional]"""
        ui.default.message(
            "If you'd like to set a preferred device type to use for MFA, enter it here.\n"
            "This is optional. valid devices types:\n"
            """
            - push - Okta Verify App push or DUO push (depends on okta supplied provider type)
            - token:software:totp - OTP using the Okta Verify App
            - token:hardware - OTP using hardware like Yubikey
            - call - OTP via Voice call
            - sms - OTP via SMS message
            - web - DUO uses localhost webbrowser to support push|call|passcode
            - passcode - DUO uses `OKTA_MFA_CODE` or `--mfa-code` if set, or prompts user for passcode(OTP).
            """
        )
        okta_username = self._get_user_input(
            "Preferred MFA Device Type", default_entry)
        return okta_username

    def _get_output_format(self, default_entry):
        """Get the user's preferred output format [Optional]"""
        ui.default.message("Set the tools' output format:[export, json]")
        output_format = None
        while output_format not in ('export', 'json'):
            output_format = self._get_user_input(
                "Preferred output format", default_entry)
        return output_format

    def _get_remember_device(self, default_entry):
        """Option to remember the MFA device"""
        ui.default.message(
            "Do you want the MFA device be remembered?\n"
            "Please answer y or n.")
        while True:
            try:
                return self._get_user_input_yes_no(
                    "Remember device", default_entry)
            except ValueError:
                ui.default.warning("Remember the MFA device must be either y or n.")

    def _get_user_input(self, message, default=None):
        """formats message to include default and then prompts user for input
        via keyboard with message. Returns user's input or if user doesn't
        enter input will return the default."""
        if default and default != '':
            prompt_message = message + " [{}]: ".format(default)
        else:
            prompt_message = message + ': '

        # print the prompt with print() rather than input() as input prompts on stderr
        user_input = self.ui.input(prompt_message)
        if user_input:
            return user_input
        return default

    def _get_user_input_yes_no(self, message, default=None):
        """works like _get_user_input, but either: return bool or
        raises ValueError"""
        if isinstance(default, str):
            default = default.lower()

        if default in ('y', 'true', True):
            default = 'y'
        else:
            default = 'n'

        answer = self._get_user_input(message, default=default)
        answer = answer.lower()

        if answer == 'y':
            return True
        if answer == 'n':
            return False

        raise ValueError('Invalid answer: %s' % answer)

    def clean_up(self):
        """ clean up secret stuff"""
        del self.username
        del self.api_key

    def fail_if_profile_not_found(self, profile_config, conf_profile, default_section):
        """
        When a users profile does not have a profile named 'DEFAULT' configparser fails to throw
        an exception. This will raise an exception that handles this case and provide better messaging
        to the user why the failure occurred.
        Ensure that whichever profile is set as the default exists in the end users okta config
        """
        if not profile_config and conf_profile == default_section:
            raise errors.GimmeAWSCredsError(
                'DEFAULT profile is missing! This is profile is required when not using --profile')