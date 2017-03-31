# Gimme AWS Creds

[![][license img]][license]
[![Build Status](https://travis-ci.org/Nike-Inc/gimme-aws-creds.svg?branch=master)](https://travis-ci.org/Nike-Inc/gimme-aws-creds)

gimme-aws-creds is a CLI that utilizes [Okta](https://www.okta.com/) IdP via SAML to acquire a temporary AWS credentials via AWS STS.

Okta is a SAML identity provider (IdP), that can be easily set-up to do SSO to your AWS console. Okta does offer an [OSS java CLI]((https://github.com/oktadeveloper/okta-aws-cli-assume-role)) tool to obtain temporary AWS credentials, but I found it needs more information than the average Okta user would have and doesn't scale well if have more than one Okta App.

With gimme-aws-creds all you need to know is your username, password, Okta url and MFA token, if MFA is enabled. gimme-aws-creds gives you the option to select which Okta AWS application and role you want credentials for. Alternatively, you can pre-configure the app and role name by passing -c or editing the config file. This is all covered in the usage section.


## Prerequisites

[Okta SAML integration to AWS](https://support.okta.com/help/articles/Knowledge_Article/Amazon-Web-Services-and-Okta-Integration-Guide?popup=true&retURL=%2Fhelp%2Fapex%2FKnowledgeArticleJson%3Fc%3DOkta_Documentation%3ATechnical_Documentation&p=101&inline=1)

Python 3

### Optional
[Cerberus](http://engineering.nike.com/cerberus/) can be used for storing the Okta API key. gimme-aws-creds uses the [Cerberus Python Client](https://github.com/Nike-Inc/cerberus-python-client) for interacting with Cerberus. It would be very easy to drop something else besides Cerberus to retrieve your API key. Otherwise, you can set the OKTA_API_KEY environment variable.


## Installation
This is a Python 3 project.

Install the gimme-aws-creds script and required python packages:
```bash
python3 setup.py install
```

## Configuration

To set-up the configuration run:
```bash
gimme-aws-creds --configure
```

A configuration wizard will prompt you to enter the necessary configuration parameters for the tool to run, the only one that is required is the idp_entry_url. The configuration file is written to ~/.okta_aws_login_config.

- idp_entry_url - This is your Okta entry url, which is typically something like https://companyname.okta.com.
- write_aws_creds - y or no - If yes, the AWS credentials will be written to ~/.aws/credentials
- cred_profile - If writting to the AWS cred file, this sets the name of the profile
- aws_appname - This is optional. The Okta AWS App name, which has the role you want to assume
- aws_rolename - This is optional. The name of the role you want temporary AWS credentials for
- cerberus_url - This is optional. This is the URL of your Cerberus instance, which can be use to store your Okta API Key.


## Usage

**If you are not using Cerberus to store your Okta API key make sure you the OKTA_API_KEY environment variable.**

After running --configure, just run gimme-aws-creds. You will be prompted for the necessary information.


```bash
$ ./gimme-aws-creds
Email address: user@domain.com
Password for user@domain.com:
Enter Google Authenticator security code: 098765
Pick an app:
[ 0 ] AWS Test Account
[ 1 ] AWS Prod Account
Selection: 1
Pick a role:
[ 0 ]: OktaAWSAdminRole
[ 1 ]: OktaAWSReadOnlyRole
Selection: 1
export AWS_ACCESS_KEY_ID=AQWERTYUIOP
export AWS_SECRET_ACCESS_KEY=T!#$JFLOJlsoddop1029405-P
```

The username and password you are prompted for are the ones you login to Okta with. You can predefine your username by setting the OKTA_USERNAME environment variable.

If you are using Cerberus, it is assumed you use the same username and password for it. If MFA is enabled you will be prompted for it.

If you have not configure an Okta App or Role, you will prompted to select one.

If all goes well you will get your temporary AWS access, secret key and token, these will either be written to stdout or ~/.aws/credentials.

You can always run ```gimme-aws-creds --help``` for all the available options.

## Running Tests

You can run all the unit tests using nosetests. Most of the tests are mocked.

```bash
$ nosetests --verbosity=2 tests/
```

## Maintenance
This project is maintained by Ann Wallace `ann.wallace@nike.com`

## Thanks and Credit
I came across [okta_aws_login](https://github.com/nimbusscale/okta_aws_login) written by Joe Keegan, when I was searching for a CLI tool that generates AWS tokens via Okta. Unfortunately it hasn't been updated since 2015 and didn't seem to work with the current Okta version. But there was still some great code I was able to reuse under the MIT license for gimme-aws-creds. I have noted in the comments where I used his code, to make sure he receives proper credit.  

## Etc.

[Okta's Java tool](https://github.com/oktadeveloper/okta-aws-cli-assume-role)

[AWS - How to Implement Federated API and CLI Access Using SAML 2.0 and AD FS](https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/)

## License
Gimme AWS Creds is released under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0)

[license]:LICENSE.txt
[license img]:https://img.shields.io/badge/License-Apache%202-blue.svg
