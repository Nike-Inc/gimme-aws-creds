# THIS IS A WORK IN PROGRESS
# gimme aws creds

gimme_aws_creds is a CLI that utilizes Okta IdP via SAML to acquire a temporary AWS credentials via AWS STS.

Okta is a SAML identity provider (IdP), that can be easily set-up to do SSO to your AWS console. Okta does offer an OSS java CLI tool to obtain temporary AWS credentials, but I found it needs more information than the average Okta user would have and doesn't scale well if have more than one Okta App.

With gimme_aws_creds all you need to know is your username, password, Okta url and MFA token, if MFA is enabled. gimme_aws_creds gives you the option to select which application you want to assume for and which role to assume. Alternatively, you can pre-configure the app and role name by passing -c or editing the config file. This is all covered in the usage section.

## Usage

```
usage: gimme_aws_creds.py [-h] [--username USERNAME] [--configure]

Gets a STS token to use for AWS CLI based on a SAML assertion from Okta

optional arguments:
  -h, --help            show this help message and exit
  --username USERNAME, -u USERNAME
                        The username to use when logging into Okta. The
                        username can also be set via the OKTA_USERNAME env
                        variable. If not provided you will be prompted to
                        enter a username.
  --configure, -c       If set, will prompt user for configuration parameters
                        and then exit.
```

## Prerequisites

[Okta SAML integration to AWS](https://support.okta.com/help/articles/Knowledge_Article/Amazon-Web-Services-and-Okta-Integration-Guide?popup=true&retURL=%2Fhelp%2Fapex%2FKnowledgeArticleJson%3Fc%3DOkta_Documentation%3ATechnical_Documentation&p=101&inline=1)

[Cerberus](http://engineering.nike.com/cerberus/) is used for storing the Okta API key, using the CerberusClient package. It would be very easy to drop something else besides Cerberus to retrieve your API key. The API key could be hardcoded in the code, but this isn't recommended.

Python 3

Install the python required packages:
```
  $ pip3 install -r requirements.txt
```


## Configuration

To set-up the configuration run:
```
gimme_aws_creds.py --configure
```

A configuration wizard will prompt you to enter the necessary configuration parameters for the tool to run, the only one that is required is the idp_entry_url.

- idp_entry_url - This is your Okta entry url, which is typically something like https://companyname.okta.com.
- aws_appname - This is optional. The Okta AWS App name, which has the role you want to assume.
- aws_rolename - This is optional. The name of the role you want temporary AWS credentials for.


### ready... set... go...
USERNAME VAR
## Thanks and Credit
https://github.com/nimbusscale/okta_aws_login Written by Joe Keegan - joe@nimbusscale.com

## Extras

[Okta's Java tool](https://github.com/oktadeveloper/okta-aws-cli-assume-role)

[AWS - How to Implement Federated API and CLI Access Using SAML 2.0 and AD FS](https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/)

## License
