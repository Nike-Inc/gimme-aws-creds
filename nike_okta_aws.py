#!/usr/bin/env python3
#this is a mash-up of :
# chris guthrie's example, aws security blog posts, my bad code and
# https://github.com/nimbusscale/okta_aws_login
#TODO
# 1. store session id
# 2. write out to an aws config file
# 3. write a web service

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
from os.path import expanduser
from urllib.parse import urlparse, urlunparse



parser = argparse.ArgumentParser(
    description = "Gets a STS token to use for AWS CLI based "
                  "on a SAML assertion from Okta")

parser.add_argument(
    '--username', '-u',
    help = "The username to use when logging into Okta. The username can "
           "also be set via the OKTA_USERNAME env variable. If not provided "
           "you will be prompted to enter a username."
)

parser.add_argument(
    '--profile', '-p',
    help = "The name of the profile to use when storing the credentials in "
           "the AWS credentials file. If not provided then the name of "
           "the role assumed will be used as the profile name."
)

parser.add_argument(
    '--verbose', '-v',
    action = 'store_true',
    help = "If set, will print a message about the AWS CLI profile "
           "that was created."
)

parser.add_argument(
    '--configure', '-c',
    action = 'store_true',
    help = "If set, will prompt user for configuration parameters "
            " and then exit."
)


args = parser.parse_args()

##########################################################################

### Variables ###
# file_root: Path in which all file interaction will be relative to.
# Defaults to the users home dir.
file_root = expanduser("~")
# okta_aws_login_config_file: The file were the config parameters for the
# okta_aws_login tool is stored
okta_aws_login_config_file = file_root + '/.okta_aws_login_config'
# okta read only API key
# TODO make this configurable
okta_api_key = '00iafWJesTyYnDAI8gtjaMaI-jHrskz9ZnB-iQJjM9'
###

def get_headers():
    headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json', 'Authorization' : 'SSWS ' + okta_api_key}
    return headers

def get_login_response(idp_entry_url,username,password):
    headers = get_headers()
    response = requests.post(idp_entry_url + '/authn', json={'username': username, 'password': password}, headers=headers)
    jresponse = json.loads(response.text)
    if 'errorCode' in jresponse:
        print("ERROR: " + jresponse['errorSummary'], "Error Code ", jresponse['errorCode'])
        sys.exit(2)
    else:
        return jresponse


# gets a list of available roles based on the aws appname provided by the user
# ask the user to select the role they want to assume and returns the selection
def get_role(login_resp,idp_entry_url,aws_appname):
    # get available roles for the AWS app
    headers = get_headers()
    user_id = login_resp['_embedded']['user']['id']
    response = requests.get(idp_entry_url + '/apps/?filter=user.id+eq+\"' +
        user_id + '\"&expand=user/' + user_id,headers=headers, verify=True)
    role_resp = json.loads(response.text)
    # Check if this is a valid response
    if 'errorCode' in role_resp:
        print("ERROR: " + role_resp['errorSummary'], "Error Code ", role_resp['errorCode'])
        sys.exit(2)
    # print out roles for the app and let the uesr select
    for app in role_resp:
        if app['label'] == aws_appname:
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

# return the app link json for select aws app
def get_app_links(login_resp,idp_entry_url,aws_appname):
    headers = get_headers()
    user_id = login_resp['_embedded']['user']['id']
    response = requests.get(idp_entry_url + '/users/' + user_id + '/appLinks',
          headers=headers, verify=True)
    app_resp = json.loads(response.text)
    if 'errorCode' in app_resp:
        print("ERROR: " + app_resp['errorSummary'], "Error Code ", app_resp['errorCode'])
        sys.exit(2)
    else:
        for app in app_resp:
            #print(app['label'])
            if(app['label'] == 'AWS_API'):
                print(app['linkUrl'])
            if app['label'] == aws_appname:
                return app

        print("ERROR no roles found for you in app: ", aws_appname)
        sys.exit(2)

# return the PrincipalArn based on the app instance id
def get_idp_arn(idp_entry_url,app_id):
    headers = get_headers()
    response = requests.get(idp_entry_url + '/apps/' + app_id ,headers=headers, verify=True)
    app_resp = json.loads(response.text)
    return app_resp['settings']['app']['identityProviderArn']

# return the base64 SAML value object from the SAML Response
def get_saml_assertion(response):
    saml_soup = BeautifulSoup(response.text, "html.parser")
    #print("SOUP", saml_soup)
    # Parse the SAML Response and grab the value
    for inputtag in saml_soup.find_all('input'):
        if (inputtag.get('name') == 'SAMLResponse'):
            return inputtag.get('value')

# return the role arn for the selected role
def get_role_arn(link_url,token,role):
    headers = get_headers()
    saml_resp = requests.get(link_url + '/?onetimetoken=' + token, headers=headers, verify=True)
    saml_value = get_saml_assertion(saml_resp)
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
        if role in chunks[1]:
            return chunks[1]

# using the assertion and arns return aws sts creds
def get_sts_creds(role_arn,idp_arn,assertion,duration=3600):
    client = boto3.client('sts')
    response = client.assume_role_with_saml(
       RoleArn=role_arn,
       PrincipalArn=idp_arn,
       SAMLAssertion=assertion,
       DurationSeconds=duration)
    return response['Credentials']

def update_config_file(okta_aws_login_config_file):
    """Prompts user for config details for the okta_aws_login tool.
    Either updates exisiting config file or creates new one."""
    config = configparser.ConfigParser()
    # See if a config file already exists.
    # If so, use current values as defaults
    if os.path.isfile(okta_aws_login_config_file) == True:
        config.read(okta_aws_login_config_file)
        idp_entry_url_default = config['DEFAULT']['idp_entry_url']
        aws_appname_default = config['DEFAULT']['aws_appname']
        output_format_default = config['DEFAULT']['output_format']
        cred_profile_default = config['DEFAULT']['cred_profile']
    # otherwise use these values for defaults
    else:
        idp_entry_url_default = ""
        aws_appname_default = "AWS Console"
        output_format_default = "json"
        cred_profile_default = "role"
    # Prompt user for config details and store in config_dict
    config_dict = {}
    # Get and validate idp_entry_url
    print("Enter the IDP Entry URL. This is https://something.okta[preview].com")
    idp_entry_url_valid = False
    while idp_entry_url_valid == False:
        idp_entry_url =  get_user_input("idp_entry_url",idp_entry_url_default)
        # Validate that idp_entry_url is a well formed okta URL
        url_parse_results = urlparse(idp_entry_url)
        if (url_parse_results.scheme == "https" and
                                     "okta.com" or "oktapreview.com" in idp_entry_url):
            idp_entry_url_valid = True
        else:
            print("idp_entry_url must be HTTPS URL for okta.com domain")
    config_dict['idp_entry_url'] = idp_entry_url
    # Get Okta AWS App name
    print('Enter AWS Okta App Name ')
    aws_appname = get_user_input("aws_appname",aws_appname_default)
    config_dict['aws_appname'] = aws_appname
    # Get and validate output_format
    print("Enter the default output format that will be configured as part of "
            "CLI profile")
    valid_formats = ["json","text","table"]
    output_format_valid = False
    while output_format_valid == False:
        output_format = get_user_input("output_format",output_format_default)
        # validate entered region is valid AWS CLI output format
        if output_format in valid_formats:
            output_format_valid = True
        else:
            print("output format must be a valid format: {}".format(
                                                            valid_formats))
    config_dict['output_format'] = output_format
    # Get and validate cred_profile
    print("cred_profile defines which profile is used to store the temp AWS "
            "creds. If set to 'role' then a new profile will be created "
            "matching the role name assumed by the user. If set to 'default' "
            "then the temp creds will be stored in the default profile")
    cred_profile_valid = False
    while cred_profile_valid == False:
        cred_profile = get_user_input("cred_profile",cred_profile_default)
        cred_profile = cred_profile.lower()
        # validate if either role or default was entered
        if cred_profile in ["default","role"]:
            cred_profile_valid = True
        else:
            print("cred_profile must be either default or role")
    config_dict['cred_profile'] = cred_profile
    # Set default config
    config['DEFAULT'] = config_dict
    with open(okta_aws_login_config_file, 'w') as configfile:
        config.write(configfile)

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

def get_user_creds():
    """Get's creds for Okta login from the user. Retruns user_creds dict"""
    # Check to see if the username arg has been set, if so use that
    if args.username is not None:
        username = args.username
    # Next check to see if the OKTA_USERNAME env var is set
    elif os.environ.get("OKTA_USERNAME") is not None:
        username = os.environ.get("OKTA_USERNAME")
    # Otherwise just ask the user
    else:
        username = input("Username: ")
    # Set prompt to include the user name, since username could be set
    # via OKTA_USERNAME env and user might not remember.
    passwd_prompt = "Password for {}: ".format(username)
    password = getpass.getpass(prompt=passwd_prompt)
    if len(password) == 0:
        print( "Password must be provided")
        sys.exit(1)
    # Build dict and return in
    user_creds = {}
    user_creds['username'] = username
    user_creds['password'] = password
    return user_creds


def main ():
    # Create/Update config when configure arg set
    if args.configure == True:
        update_config_file(okta_aws_login_config_file)
        sys.exit()
    # Check to see if config file exists, if not complain and exit
    # If config file does exist create config dict from file
    if os.path.isfile(okta_aws_login_config_file):
        config = configparser.ConfigParser()
        config.read(okta_aws_login_config_file)
        conf_dict = dict(config['DEFAULT'])
    else:
        print(".okta_aws_login_config is needed. Use --configure flag to "
                "generate file.")
        sys.exit(1)

    user_creds = get_user_creds()
    username = user_creds['username']
    password = user_creds['password']
    idp_entry_url = conf_dict['idp_entry_url'] + '/api/v1'
    aws_appname = conf_dict['aws_appname']
    headers = get_headers()

    resp = get_login_response(idp_entry_url,username,password)
    session = requests.session()
    # get available roles for the AWS app
    role = get_role(resp,idp_entry_url,aws_appname)
    # get the applinks available to the user
    app_links = get_app_links(resp,idp_entry_url,aws_appname)
    # Get the the identityProviderArn from the aws app
    idp_arn = get_idp_arn(idp_entry_url,app_links['appInstanceId'])
    # Get the role ARNs
    role_arn = get_role_arn(app_links['linkUrl'],resp['sessionToken'],role)
    # get a new token for aws_creds
    login_res = get_login_response(idp_entry_url,username,password)
    resp2 = requests.get(app_links['linkUrl'] + '/?sessionToken=' + login_res['sessionToken'], verify=True)
    session = requests.session()
    assertion = get_saml_assertion(resp2)
    aws_creds = get_sts_creds(role_arn,idp_arn,assertion)
    print("AccessKeyId:",aws_creds['AccessKeyId'])
    print("SecretAccessKey:",aws_creds['SecretAccessKey'])

    # delete creds
    del username
    del password
    del user_creds

    sys.exit(0)

if __name__ == '__main__':
    main()
