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
import base64
# standard imports
import configparser
import os
from os.path import expanduser
import re
import sys
import xml.etree.ElementTree as ET
from collections import namedtuple


# extras
import boto3
from okta.framework.ApiClient import ApiClient
from okta.framework.OktaError import OktaError

# local imports
from gimme_aws_creds.config import Config
from gimme_aws_creds.okta import OktaClient


RoleSet = namedtuple('RoleSet', 'idp, role')


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
         -h, --help     show this help message and exit
         --username USERNAME, -u USERNAME
                        The username to use when logging into Okta. The
                        username can also be set via the OKTA_USERNAME env
                        variable. If not provided you will be prompted to
                        enter a username.
         -k, --insecure Allow connections to SSL sites without cert verification
         -c, --configure
                        If set, will prompt user for configuration
                        parameters and then exit.
         --profile PROFILE, -p PROFILE
                        If set, the specified configuration profile will
                        be used instead of the default profile.

        Config Options:
           okta_org_url = Okta URL
           gimme_creds_server = URL of the gimme-creds-server
           client_id = OAuth Client id for the gimme-creds-server
           okta_auth_server = Server ID for the OAuth authorization server used by gimme-creds-server
           write_aws_creds = Option to write creds to ~/.aws/credentials
           cred_profile = Use DEFAULT or Role as the profile in ~/.aws/credentials
           aws_appname = (optional) Okta AWS App Name
           aws_rolename =  (optional) AWS Role ARN. 'ALL' will retrieve all roles.
    """
    FILE_ROOT = expanduser("~")
    AWS_CONFIG = FILE_ROOT + '/.aws/credentials'

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

        # Write the updated config file
        with open(self.AWS_CONFIG, 'w+') as configfile:
            config.write(configfile)

    @staticmethod
    def _enumerate_saml_roles(assertion):
        """ using the assertion and arns return aws sts creds """
        role_pairs = []
        root = ET.fromstring(base64.b64decode(assertion))
        for saml2_attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
            if saml2_attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role':
                for saml2_attribute_value in saml2_attribute.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
                    role_pairs.append(saml2_attribute_value.text)

        # Normalize pieces of string; order may vary per AWS sample
        result = []
        for role_pair in role_pairs:
            idp, role = None, None
            for field in role_pair.split(','):
                if 'saml-provider' in field:
                    idp = field
                elif 'role' in field:
                    role = field
            if not idp or not role:
                print('Parsing error on {}'.format(role_pair))
                exit()
            else:
                result.append(RoleSet(idp=idp, role=role))

        return result

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
            print("No AWS accounts found.")
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
                print("Error: " + username + " was not found!")
                exit(1)
            else:
                print("Error: " + e.error_summary)
                exit(1)

        try:
            # Get first page of results
            result = users_client.get_path('/{0}/appLinks'.format(user['id']))
            final_result = result.json()

            # Loop through other pages
            while 'next' in result.links:
                result = app_client.get(result.links['next']['url'])
                final_result = final_result + result.json()
            print("done\n")
        except OktaError as e:
            if e.error_code == 'E0000007':
                print("Error: No applications found for " + username)
                exit(1)
            else:
                print("Error: " + e.error_summary)
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
            print("No AWS accounts found.")
            exit()

        return app_list

    def _choose_app(self, aws_info):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection
        """
        if not aws_info:
            return None

        app_strs = []
        for i, app in enumerate(aws_info):
            app_strs.append('[{}] {}'.format(i, app["name"]))

        if app_strs:
            print("Pick an app:")
            # print out the apps and let the user select
            for app in app_strs:
                print(app)
        else:
            return None

        selection = self._get_user_int_selection(0, len(aws_info)-1)

        if selection is None:
            print("You made an invalid selection")
            exit(1)

        return aws_info[int(selection)]

    def _get_selected_app(self, aws_appname, aws_info):
        """ select the application from the config file if it exists in the
        results from Okta.  If not, present the user with a menu."""

        if aws_appname:
            for _, app in enumerate(aws_info):
                if app["name"] == aws_appname:
                    return app
            print("ERROR: AWS account [{}] not found!".format(aws_appname))

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
            print("ERROR: AWS role [{}] not found!".format(aws_rolename))

        # Present the user with a list of roles to choose from
        return self._choose_role(aws_roles)

    def _choose_role(self, roles):
        """ gets a list of available roles and
        asks the user to select the role they want to assume
        """
        if not roles:
            return None

        # Gather the roles available to the user.
        role_strs = []
        for i, role in enumerate(roles):
            if not role:
                continue
            role_strs.append('[{}] {}'.format(i, role.role))

        if role_strs:
            print("Pick a role:")
            for role in role_strs:
                print(role)
        else:
            return None

        selection = self._get_user_int_selection(0, len(roles)-1)

        if selection is None:
            print("You made an invalid selection")
            exit(1)

        return roles[int(selection)].role

    @staticmethod
    def _get_user_int_selection(min_int, max_int, max_retries=5):
        selection = None
        for _ in range(0, max_retries):
            try:
                selection = int(input("Selection: "))
                break
            except ValueError:
                print('Invalid selection, must be an integer value.')

        if selection is None:
            return None

        # make sure the choice is valid
        if selection < min_int or selection > max_int:
            return None

        return selection

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

        if not conf_dict.get('okta_org_url'):
            print('No Okta organization URL in configuration.  Try running --config again.')
            exit(1)

        if not conf_dict.get('gimme_creds_server'):
            print('No Gimme-Creds server URL in configuration.  Try running --config again.')
            exit(1)

        okta = OktaClient(conf_dict['okta_org_url'], config.verify_ssl_certs)
        if config.username is not None:
            okta.set_username(config.username)

        # Call the Okta APIs and proces data locally
        if conf_dict.get('gimme_creds_server') == 'internal':
            # Okta API key is required when calling Okta APIs internally
            if config.api_key is None:
                print('OKTA_API_KEY environment variable not found!')
                exit(1)
            # Authenticate with Okta
            auth_result = okta.auth_session()

            print("Authentication Success! Getting AWS Accounts")
            aws_results = self._get_aws_account_info(conf_dict['okta_org_url'], config.api_key, auth_result['username'])

        # Use the gimme_creds_lambda service
        else:
            if not conf_dict.get('client_id'):
                print('No OAuth Client ID in configuration.  Try running --config again.')
            if not conf_dict.get('okta_auth_server'):
                print('No OAuth Authorization server in configuration.  Try running --config again.')

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

            print("Authentication Success! Calling Gimme-Creds Server...")
            aws_results = self._call_gimme_creds_server(okta, conf_dict['gimme_creds_server'])

        aws_app = self._get_selected_app(conf_dict.get('aws_appname'), aws_results)
        saml_data = okta.get_saml_response(aws_app['links']['appLink'])
        roles = self._enumerate_saml_roles(saml_data['SAMLResponse'])
        aws_role = self._get_selected_role(conf_dict.get('aws_rolename'), roles)
        aws_partition = self._get_partition_from_saml_acs(saml_data['TargetUrl'])

        for _, role in enumerate(roles):
            # Skip irrelevant roles
            if aws_role != 'all' and aws_role not in role.role:
                continue

            aws_creds = self._get_sts_creds(aws_partition, saml_data['SAMLResponse'], role.idp, role.role)
            deriv_profname = re.sub('arn:aws:iam:.*/', '', role.role)

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
                print('writing role {} to {}'.format(role.role, self.AWS_CONFIG))
                self._write_aws_creds(
                    profile_name,
                    aws_creds['AccessKeyId'],
                    aws_creds['SecretAccessKey'],
                    aws_creds['SessionToken']
                )
            else:
                #Print out temporary AWS credentials.  Credentials are printed to stderr to simplify
                #redirection for use in automated scripts
                print("\nexport AWS_PROFILE=" + deriv_profname, file=sys.stderr)
                print("export AWS_ACCESS_KEY_ID=" + aws_creds['AccessKeyId'], file=sys.stderr)
                print("export AWS_SECRET_ACCESS_KEY=" + aws_creds['SecretAccessKey'], file=sys.stderr)
                print("export AWS_SESSION_TOKEN=" + aws_creds['SessionToken'], file=sys.stderr)

        config.clean_up()
