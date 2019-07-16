#!/usr/bin/env python3
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
# For enumerating saml roles
# standard imports
import configparser
import os
import re
import sys
from os.path import expanduser

# extras
import boto3
from botocore.exceptions import ClientError
from okta.framework.ApiClient import ApiClient
from okta.framework.OktaError import OktaError

from gimme_aws_creds.aws import AwsResolver
# local imports
from gimme_aws_creds.config import Config
from gimme_aws_creds.default import DefaultResolver
from gimme_aws_creds.okta import OktaClient


class GimmeAWSCreds(object):
    """
       This is a CLI tool that gets temporary AWS credentials
       from Okta based the available AWS Okta Apps and roles
       assigned to the user. The user is able to select the app
       and role from the CLI or specify them in a config file by
       passing --configure to the CLI too.
       gimme_aws_creds will either write the credentials to stdout
       or ~/.aws/credentials depending on what was specified when
       --configure was ran.

       Usage:
          -h, --help            show this help message and exit
          --username USERNAME, -u USERNAME
                                The username to use when logging into Okta. The
                                username can also be set via the OKTA_USERNAME env
                                variable. If not provided you will be prompted to
                                enter a username.
          --configure, -c       If set, will prompt user for configuration parameters
                                and then exit.
          --profile PROFILE, -p PROFILE
                                If set, the specified configuration profile will be
                                used instead of the default.
          --resolve, -r         If set, perfom alias resolution.
          --insecure, -k        Allow connections to SSL sites without cert
                                verification.
          --mfa-code MFA_CODE   The MFA verification code to be used with SMS or TOTP
                                authentication methods. If not provided you will be
                                prompted to enter an MFA verification code.
          --remember-device, -m
                                The MFA device will be remembered by Okta service for
                                a limited time, otherwise, you will be prompted for it
                                every time.
          --version             gimme-aws-creds version

        Config Options:
           okta_org_url = Okta URL
           gimme_creds_server = URL of the gimme-creds-server
           client_id = OAuth Client id for the gimme-creds-server
           okta_auth_server = Server ID for the OAuth authorization server used by gimme-creds-server
           write_aws_creds = Option to write creds to ~/.aws/credentials
           cred_profile = Use DEFAULT or Role as the profile in ~/.aws/credentials
           aws_appname = (optional) Okta AWS App Name
           aws_rolename =  (optional) AWS Role ARN. 'ALL' will retrieve all roles.
           okta_username = (optional) Okta User Name
    """
    FILE_ROOT = expanduser("~")
    AWS_CONFIG = os.environ.get('AWS_SHARED_CREDENTIALS_FILE', os.path.join(FILE_ROOT, '.aws/credentials'))
    resolver = DefaultResolver()
    envvar_list = ['OKTA_AUTH_SERVER', 'CLIENT_ID',
                   'OKTA_USERNAME', 'AWS_DEFAULT_DURATION',
                   'CRED_PROFILE']

    #  this is modified code from https://github.com/nimbusscale/okta_aws_login
    def _write_aws_creds(self, profile, access_key, secret_key, token):
        """ Writes the AWS STS token into the AWS credential file"""
        # Check to see if the aws creds path exists, if not create it
        creds_dir = os.path.dirname(self.AWS_CONFIG)
        if os.path.exists(creds_dir) is False:
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
        config.set(profile, 'aws_security_token', token)

        # Write the updated config file
        with open(self.AWS_CONFIG, 'w+') as configfile:
            config.write(configfile)

    @staticmethod
    def _get_partition_from_saml_acs(saml_acs_url):
        """ Determine the AWS partition by looking at the ACS endpoint URL"""
        if saml_acs_url == 'https://signin.aws.amazon.com/saml':
            return 'aws'
        elif saml_acs_url == 'https://signin.amazonaws.cn/saml':
            return 'aws-cn'
        elif saml_acs_url == 'https://signin.amazonaws-us-gov.com/saml':
            return 'aws-us-gov'
        else:
            print("{} is an unknown ACS URL".format(saml_acs_url))
            sys.exit(1)

    @staticmethod
    def _get_sts_creds(partition, assertion, idp, role, duration=3600):
        """ using the assertion and arns return aws sts creds """

        # Use the first available region for partitions other than the public AWS
        if partition != 'aws':
            regions = boto3.session.Session().get_available_regions('sts', partition)
            client = boto3.client('sts', regions[0])
        else:
            client = boto3.client('sts')

        response = client.assume_role_with_saml(
            RoleArn=role,
            PrincipalArn=idp,
            SAMLAssertion=assertion,
            DurationSeconds=duration
        )

        return response['Credentials']

    @staticmethod
    def _call_gimme_creds_server(okta_connection, gimme_creds_server_url):
        """ Retrieve the user's AWS accounts from the gimme_creds_server"""
        response = okta_connection.get(gimme_creds_server_url)

        # Throw an error if we didn't get any accounts back
        if not response.json():
            print("No AWS accounts found.", file=sys.stderr)
            exit()

        return response.json()

    @staticmethod
    def _get_aws_account_info(okta_org_url, okta_api_key, username):
        """ Call the Okta User API and process the results to return
        just the information we need for gimme_aws_creds"""
        # We need access to the entire JSON response from the Okta APIs, so we need to
        # use the low-level ApiClient instead of UsersClient and AppInstanceClient
        users_client = ApiClient(okta_org_url, okta_api_key, pathname='/api/v1/users')

        # Get User information
        try:
            result = users_client.get_path('/{0}'.format(username))
            user = result.json()
        except OktaError as e:
            if e.error_code == 'E0000007':
                print("Error: " + username + " was not found!", file=sys.stderr)
                exit(1)
            else:
                print("Error: " + e.error_summary, file=sys.stderr)
                exit(1)

        try:
            # Get first page of results
            result = users_client.get_path('/{0}/appLinks'.format(user['id']))
            final_result = result.json()

            # Loop through other pages
            while 'next' in result.links:
                result = users_client.get(result.links['next']['url'])
                final_result = final_result + result.json()
            print("done\n", file=sys.stderr)
        except OktaError as e:
            if e.error_code == 'E0000007':
                print("Error: No applications found for " + username, file=sys.stderr)
                exit(1)
            else:
                print("Error: " + e.error_summary, file=sys.stderr)
                exit(1)

        # Loop through the list of apps and filter it down to just the info we need
        app_list = []
        for app in final_result:
            # All AWS connections have the same app name
            if (app['appName'] == 'amazon_aws'):
                newAppEntry = {}
                newAppEntry['id'] = app['id']
                newAppEntry['name'] = app['label']
                newAppEntry['links'] = {}
                newAppEntry['links']['appLink'] = app['linkUrl']
                newAppEntry['links']['appLogo'] = app['logoUrl']
                app_list.append(newAppEntry)

        # Throw an error if we didn't get any accounts back
        if not app_list:
            print("No AWS accounts found.", file=sys.stderr)
            exit()

        return app_list

    def _choose_app(self, aws_info):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection
        """
        if not aws_info:
            return None

        if len(aws_info) == 1:
            return aws_info[0]	# auto select when only 1 choice

        app_strs = []
        for i, app in enumerate(aws_info):
            app_strs.append('[{}] {}'.format(i, app["name"]))

        if app_strs:
            print("Pick an app:", file=sys.stderr)
            # print out the apps and let the user select
            for app in app_strs:
                print(app, file=sys.stderr)
        else:
            return None

        selection = self._get_user_int_selection(0, len(aws_info)-1)

        if selection is None:
            print("You made an invalid selection", file=sys.stderr)
            exit(1)

        return aws_info[int(selection)]

    def _get_selected_app(self, aws_appname, aws_info):
        """ select the application from the config file if it exists in the
        results from Okta.  If not, present the user with a menu."""

        if aws_appname:
            for _, app in enumerate(aws_info):
                if app["name"] == aws_appname:
                    return app
                elif app["name"] == "fakelabel":
                    # auto select this app
                    return app
            print("ERROR: AWS account [{}] not found!".format(aws_appname), file=sys.stderr)

        # Present the user with a list of apps to choose from
        return self._choose_app(aws_info)

    def _get_selected_role(self, aws_rolename, aws_roles):
        """ select the role from the config file if it exists in the
        results from Okta.  If not, present the user with a menu. """

        # 'all' is a special case - skip procesing
        if aws_rolename == 'all':
            return aws_rolename
        # check to see if a role is in the config and look for it in the results from Okta
        if aws_rolename:
            for _, role in enumerate(aws_roles):
                if aws_rolename == role.role:
                    return aws_rolename
            print("ERROR: AWS role [{}] not found!".format(aws_rolename), file=sys.stderr)

        # Present the user with a list of roles to choose from
        return self._choose_role(aws_roles)

    def _choose_role(self, roles):
        """ gets a list of available roles and
        asks the user to select the role they want to assume
        """
        if not roles:
            return None

        # Check if only one role exists and return that role
        if len(roles) == 1:
            single_role = roles[0].role
            print("Detected single role: {}".format(single_role), file=sys.stderr)
            return single_role

        # Gather the roles available to the user.
        role_strs = self.resolver._display_role(roles)

        if role_strs:
            print("Pick a role:", file=sys.stderr)
            for role in role_strs:
                print(role, file=sys.stderr)
        else:
            return None

        selection = self._get_user_int_selection(0, len(roles)-1)

        if selection is None:
            print("You made an invalid selection", file=sys.stderr)
            exit(1)

        return roles[int(selection)].role

    @staticmethod
    def _get_user_int_selection(min_int, max_int, max_retries=5):
        selection = None
        for _ in range(0, max_retries):
            try:
                print("Selection: ", end="", file=sys.stderr)
                selection = int(input())
                break
            except ValueError:
                print('Invalid selection, must be an integer value.', file=sys.stderr)

        if selection is None:
            return None

        # make sure the choice is valid
        if selection < min_int or selection > max_int:
            return None

        return selection

    def _overwrite_with_envvars(self, configuration_dict):
        for value in self.envvar_list:
            if (os.environ.get(value)):
                configuration_dict[value.lower()] = os.environ.get(value)
        return configuration_dict

    def run(self):
        """ Pulling it all together to make the CLI """
        config = Config()
        config.get_args()
        # Create/Update config when configure arg set
        if config.configure is True:
            config.update_config_file()
            exit()

        # get the config dict
        conf_dict = config.get_config_dict()
        conf_dict = self._overwrite_with_envvars(conf_dict)

        if not conf_dict.get('okta_org_url'):
            print('No Okta organization URL in configuration.  Try running --config again.', file=sys.stderr)
            exit(1)

        if not conf_dict.get('gimme_creds_server'):
            print('No Gimme-Creds server URL in configuration.  Try running --config again.', file=sys.stderr)
            exit(1)

        if config.register_device is True:
            conf_dict['device_token'] = None
        else:
            if not conf_dict.get('device_token'):
                print('No device token in configuration.  Try running --register_device again.', file=sys.stderr)
                exit(1)

        okta = OktaClient(conf_dict['okta_org_url'], config.verify_ssl_certs, conf_dict['device_token'])
        if config.resolve is True:
            self.resolver = AwsResolver(config.verify_ssl_certs)
        else:
            if conf_dict.get('resolve_aws_alias') and str(conf_dict['resolve_aws_alias']) == 'True':
                self.resolver = AwsResolver(config.verify_ssl_certs)

        if config.username is not None:
            okta.set_username(config.username)
        else:
            if conf_dict.get('okta_username'):
                okta.set_username(conf_dict['okta_username'])

        if conf_dict.get('preferred_mfa_type'):
            okta.set_preferred_mfa_type(conf_dict['preferred_mfa_type'])

        if config.mfa_code is not None:
            okta.set_mfa_code(config.mfa_code)

        okta.set_remember_device(config.remember_device
                                 or conf_dict.get('remember_device', False))

        # AWS Default session duration ....
        if conf_dict.get('aws_default_duration'):
            config.aws_default_duration = int(conf_dict['aws_default_duration'])
        else:
            config.aws_default_duration = 3600

        # Capture the Device Token and write it to the config file
        if config.register_device is True:
            auth_result = okta.auth_session()
            conf_dict['device_token'] = auth_result['device_token']
            config.write_config_file(conf_dict)
            print('Device token saved!', file=sys.stderr)
            sys.exit()
        else:

            # Call the Okta APIs and proces data locally
            if conf_dict.get('gimme_creds_server') == 'internal':
                # Okta API key is required when calling Okta APIs internally
                if config.api_key is None:
                    print('OKTA_API_KEY environment variable not found!', file=sys.stderr)
                    exit(1)
                auth_result = okta.auth_session()
                aws_results = self._get_aws_account_info(conf_dict['okta_org_url'], config.api_key, auth_result['username'])

            elif conf_dict.get('gimme_creds_server') == 'appurl':
                auth_result = okta.auth_session()
                # bypass lambda & API call
                # Apps url is required when calling with appurl
                if conf_dict.get('app_url'):
                    config.app_url = conf_dict['app_url']
                if config.app_url is None:
                    print('app_url is not defined in your config !', file=sys.stderr)
                    exit(1)

                # build app list
                aws_results = []
                newAppEntry = {}
                newAppEntry['id'] = "fakeid"  # not used anyway
                newAppEntry['name'] = "fakelabel" #not used anyway
                newAppEntry['links'] = {}
                newAppEntry['links']['appLink'] = config.app_url
                aws_results.append(newAppEntry)

            # Use the gimme_creds_lambda service
            else:
                if not conf_dict.get('client_id'):
                    print('No OAuth Client ID in configuration.  Try running --config again.', file=sys.stderr)
                if not conf_dict.get('okta_auth_server'):
                    print('No OAuth Authorization server in configuration.  Try running --config again.', file=sys.stderr)

                # Authenticate with Okta and get an OAuth access token
                okta.auth_oauth(
                    conf_dict['client_id'],
                    authorization_server=conf_dict['okta_auth_server'],
                    access_token=True,
                    id_token=False,
                    scopes=['openid']
                )

                # Add Access Tokens to Okta-protected requests
                okta.use_oauth_access_token(True)

                print("Authentication Success! Calling Gimme-Creds Server...", file=sys.stderr)
                aws_results = self._call_gimme_creds_server(okta, conf_dict['gimme_creds_server'])

            aws_app = self._get_selected_app(conf_dict.get('aws_appname'), aws_results)
            saml_data = okta.get_saml_response(aws_app['links']['appLink'])
            roles = self.resolver._enumerate_saml_roles(saml_data['SAMLResponse'], saml_data['TargetUrl'])
            aws_role = self._get_selected_role(conf_dict.get('aws_rolename'), roles)
            aws_partition = self._get_partition_from_saml_acs(saml_data['TargetUrl'])

        for _, role in enumerate(roles):
            # Skip irrelevant roles
            if aws_role != 'all' and aws_role != role.role:
                continue

            try:
                aws_creds = self._get_sts_creds(aws_partition, saml_data['SAMLResponse'], role.idp, role.role, config.aws_default_duration)
            except ClientError as ex:
                if ex.response['Error']['Message'] == 'The requested DurationSeconds exceeds the MaxSessionDuration set for this role.':
                    print("The requested session duration was too long for this role.  Falling back to 1 hour.", file=sys.stderr)
                    aws_creds = self._get_sts_creds(aws_partition, saml_data['SAMLResponse'], role.idp, role.role, 3600)

            #TODO: Make this regex work for GovCloud ARNs too
            deriv_profname = re.sub('arn:(aws|aws-cn):iam:.*/', '', role.role)

            # check if write_aws_creds is true if so
            # get the profile name and write out the file
            if str(conf_dict['write_aws_creds']) == 'True':
                # set the profile name
                # Note if there are multiple roles, and 'default' is
                # selected it will be overwritten multiple times and last role
                # wins.
                if conf_dict['cred_profile'].lower() == 'default':
                    profile_name = 'default'
                elif conf_dict['cred_profile'].lower() == 'role':
                    profile_name = deriv_profname
                else:
                    profile_name = conf_dict['cred_profile']

                # Write out the AWS Config file
                print('writing role {} to {}'.format(role.role, self.AWS_CONFIG), file=sys.stderr)
                self._write_aws_creds(
                    profile_name,
                    aws_creds['AccessKeyId'],
                    aws_creds['SecretAccessKey'],
                    aws_creds['SessionToken']
                )
            else:
                #Print out temporary AWS credentials.  Credentials are printed to stderr to simplify
                #redirection for use in automated scripts
                print("export AWS_ACCESS_KEY_ID=" + aws_creds['AccessKeyId'])
                print("export AWS_SECRET_ACCESS_KEY=" + aws_creds['SecretAccessKey'])
                print("export AWS_SESSION_TOKEN=" + aws_creds['SessionToken'])
                print("export AWS_SECURITY_TOKEN=" + aws_creds['SessionToken'])

        config.clean_up()
