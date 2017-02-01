# gimme_aws_creds

gimme_aws_creds is a CLI that utilizes Okta IdP via SAML to acquire a temporary AWS credentials via AWS STS.

Okta is a SAML identity provider (IdP), that can be easily set-up to do SSO to your AWS console. Okta does offer an OSS java CLI tool to obtain temporary AWS credentials, but I found it needs more information than the average Okta user would have and doesn't scale well if have more than one Okta App.

With gimme_aws_creds all you need to know is your username, password, Okta url and MFA token, if MFA is enabled. gimme_aws_creds gives you the option to select which application you want to assume for and which role to assume. Alternatively, you can pre-configure the app and role name by passing -c or editing the config file. This is all covered in the usage section.


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

A configuration wizard will prompt you to enter the necessary configuration parameters for the tool to run, the only one that is required is the idp_entry_url. The configuration file is written to ~/.okta_aws_login_config.

- idp_entry_url - This is your Okta entry url, which is typically something like https://companyname.okta.com.
- aws_appname - This is optional. The Okta AWS App name, which has the role you want to assume.
- aws_rolename - This is optional. The name of the role you want temporary AWS credentials for.


## Usage

After running --configure, just run gimme_aws_creds.py. You will be prompted for the necessary information.

```
$ ./gimme_aws_creds.py
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

If all goes well you will get your temporary AWS access and secret key.

You can always run ```gimme_aws_creds.py --help``` for all the available options.


## Thanks and Credit
I came across [okta_aws_login](https://github.com/nimbusscale/okta_aws_login) written by Joe Keegan, when I was searching for a CLI tool that generates AWS tokens via Okta. Unfortunately it hasn't been updated since 2015 and didn't seem to work with the current Okta version. But there was still some great code I was able to reuse under the MIT license for gimme_aws_creds. I have noted in the comments where I used his code, to make sure he receives proper credit.  

## Etc.

[Okta's Java tool](https://github.com/oktadeveloper/okta-aws-cli-assume-role)

[AWS - How to Implement Federated API and CLI Access Using SAML 2.0 and AD FS](https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/)

## License
