# THIS IS A WORK IN PROGRESS 
# gimme aws creds

gimme_aws_creds is a CLI that utilizes Okta IdP via SAML to acquire a temporary AWS credentials via AWS STS.

Okta is a SAML identity provider (IdP), that can be easily set-up to do SSO to your AWS console. Okta does offer an OSS java CLI tool to obtain temporary AWS credentials, but I found it needs more information than the average Okta user would have and doesn't scale well if have more than one Okta App.

With gimme_aws_creds all you need to know is your username, password, Okta url and MFA token, if MFA is enabled. gimme_aws_creds gives you the option to select which application you want to assume for and which role to assume. Alternatively, you can pre-configure the app and role name by passing -c or editing the config file. This is all covered in the usage section.

## Usage

### Prerequisites

[Okta SAML integration to AWS](https://support.okta.com/help/articles/Knowledge_Article/Amazon-Web-Services-and-Okta-Integration-Guide?popup=true&retURL=%2Fhelp%2Fapex%2FKnowledgeArticleJson%3Fc%3DOkta_Documentation%3ATechnical_Documentation&p=101&inline=1)

[Cerberus](http://engineering.nike.com/cerberus/) is used for storing Okta API keys.The API keys could be hardcoded in the code, but this isn't recommended.

Python 3

Install the python required modules:
  $ pip3 install requirements.txt

### uses cerberus

### run the config

config file HERE

USERNAME VAR

### ready... set... go...

## Thanks and Credit
https://github.com/nimbusscale/okta_aws_login Written by Joe Keegan - joe@nimbusscale.com

## Extras

[Okta's Java tool](https://github.com/oktadeveloper/okta-aws-cli-assume-role)

[AWS - How to Implement Federated API and CLI Access Using SAML 2.0 and AD FS](https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/)

## License
