#!/usr/bin/env python3
import argparse
import boto3
import configparser
import getpass
import json
import os
import re
import requests
import sys
#import yaml
from bs4 import BeautifulSoup
from os.path import expanduser
from urllib.parse import urlparse, urlunparse

#this is a mash-up of :
# https://wiki.cis.nike.com/display/SAE/Okta+AssumeRoleWithSAML and
# https://github.com/nimbusscale/okta_aws_login
#TODO
#1. get API key
#2. get app name
#2a. get role arn
#3. be able to select which role you want to use


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
# sid_cache_file: The file where the Okta sid is stored.
# only used if cache_sid is True.
sid_cache_file = file_root + '/.okta_sid'
###


def chris(username,password,idp_entry_url,aws_appname):
    idp_entry_url += '/api/v1'
    print("idp_entry_url", idp_entry_url)
    headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json', 'Authorization' : 'SSWS ' + 'YOUR OKTA API KEY'}

    r = requests.post(idp_entry_url + '/authn', json={'username': username, 'password': password}, headers=headers)

    resp = json.loads(r.text)
    print("resp", resp)
    if 'errorCode' in resp:
        print("ERROR: " + resp['errorSummary'])
    elif 'status' in resp and resp['status'] == 'SUCCESS':
        print("Successful Login")
        session = requests.session()

        # get available roles for the AWS app
        role_req = requests.get(idp_entry_url + '/apps/?filter=user.id+eq+\"' +
            resp['_embedded']['user']['id'] + '\"&expand=user/' + resp['_embedded']['user']['id'],
            headers=headers, verify=True)
        ## TODO Check this a 200
        print (role_req)
        role_resp = json.loads(role_req.text)
        #print("ROLE", role_resp )
        for app in role_resp:
            if app['label'] == aws_appname:
                # TODO make this interactive
                print ("pick a role:")
                for i, role in enumerate(app['_embedded']['user']['profile']['samlRoles']):
                    print ('[',i,']:', role)

        # get the applinks available to the user
        print ("r2 looks like", idp_entry_url + '/users/'+ resp['_embedded']['user']['id'] + '/appLinks')
        r2 = requests.get(idp_entry_url + '/users/' + resp['_embedded']['user']['id'] + '/appLinks',
                          headers=headers, verify=True)
        if 'errorCode' in r2:
            print("ERROR: " + r2['errorSummary'], "Error Code ", r2['errorCode'])
            sys.exit(2)
        else:
            print("r2", r2)
            app_resp = json.loads(r2.text)
            print("app reponse", app_resp)
            for app in app_resp:
                print(app['label'])
                if(app['label'] == 'AWS_API'):
                    print(app['linkUrl'])
                if app['label'] == aws_appname:
                    # for some reason -admin is getting added to ${org} in the linkUL this is a hack to remove it
                    # http://developer.okta.com/docs/api/resources/users.html#get-assigned-app-links
                    app['linkUrl'] = re.sub('-admin','', app['linkUrl'])
                    print("APP LABEL MATCH")
                    print("APP", app)
                    sso_url = app['linkUrl'] + '/?sessionToken=' + resp['sessionToken']
                    print("sso_url", app['linkUrl'] + '/?sessionToken=' + resp['sessionToken'])
                    response = session.get(sso_url, verify=True)
                    print ("response app", response)

                    soup = BeautifulSoup(response.text, "html.parser")
                    assertion = ''

                    # Get the the identityProviderArn from the aws app
                    ##print ('APP ID', app['appInstanceId'])
                    ##print ('APP GET', idp_entry_url + '/apps/' + app['appInstanceId'] )
                    app_rq = requests.get(idp_entry_url + '/apps/' + app['appInstanceId'],headers=headers, verify=True)
                    app_rp = json.loads(app_rq.text)
                    idp_arn = app_rp['settings']['app']['identityProviderArn']

                    #print("SOUP", soup)
                    # Look for the SAMLResponse attribute of the input tag (determined by
                    # analyzing the debug print lines above)
                    for inputtag in soup.find_all('input'):
                        if (inputtag.get('name') == 'SAMLResponse'):
                            #print(inputtag.get('value'))
                            assertion = inputtag.get('value')
                            #print(assertion)
                            client = boto3.client('sts')
                            response = client.assume_role_with_saml(
                            RoleArn='arn:aws:iam::107274433934:role/OktaAWSAdminRole',
                            PrincipalArn=idp_arn,
                            SAMLAssertion=assertion,
                            DurationSeconds=3600
                            )
                            print("AccessKeyId:",response['Credentials']['AccessKeyId'])
                            print("SecretAccessKey:", response['Credentials']['SecretAccessKey'])
                            sys.exit(0)

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
        cache_sid_default = config['DEFAULT']['cache_sid']
        cred_profile_default = config['DEFAULT']['cred_profile']
    # otherwise use these values for defaults
    else:
        idp_entry_url_default = ""
        aws_appname_default = "AWS Console"
        output_format_default = "json"
        cache_sid_default = "yes"
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
    # Get and validate cache_sid
    print("cache_sid determines if the session id from Okta should be saved "
            "to a local file. If enabled it allows for new tokens to be "
            "retrieved without a login to Okta for the lifetime of the "
            "session. Either 'yes' or 'no'")
    cache_sid_valid = False
    while cache_sid_valid == False:
        cache_sid = get_user_input("cache_sid",cache_sid_default)
        cache_sid = cache_sid.lower()
        # validate if either true or false were entered
        if cache_sid in ["yes","y"]:
            cache_sid = "yes"
            cache_sid_valid = True
        elif cache_sid in ["no","n"]:
            cache_sid = "no"
            cache_sid_valid = True
        else:
            print("cache_sid must be either yes or no")
    config_dict['cache_sid'] = cache_sid
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
    ## remove
    print (password)
    return user_creds

def get_sid_from_file(sid_cache_file):
    """Checks to see if a file exists at the provided path. If so file is read
    and checked to see if the contents looks to be a valid sid.
    if so sid is returned"""
    if os.path.isfile(sid_cache_file) == True:
        with open(sid_cache_file) as sid_file:
            sid = sid_file.read()
            if len(sid) == 25:
                return sid

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
    assertion = None
    # if sid cache is enabled, see if a sid file exists
    if conf_dict['cache_sid'] == "yes":
        sid = get_sid_from_file(sid_cache_file)
    else:
        sid = None
    # If a sid has been set from file then attempt login via the sid
    if sid is not None:
        response = okta_cookie_login(sid,conf_dict['idp_entry_url'])
        assertion = get_saml_assertion(response)
    # if the assertion equals None, means there was no sid, the sid expired
    # or is otherwise invalid, so do a password login
    if assertion is None:
        # If sid file exists, remove it because the contained sid has expired
        if os.path.isfile(sid_cache_file):
            os.remove(sid_cache_file)
        user_creds = get_user_creds()
        chris(user_creds['username'],user_creds['password'],conf_dict['idp_entry_url'],conf_dict['aws_appname'])


if __name__ == '__main__':
    main()
