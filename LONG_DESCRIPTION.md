# Gimme AWS Creds

gimme-aws-creds is a CLI that utilizes an [Okta](https://www.okta.com/) IdP via SAML to acquire temporary AWS credentials via AWS STS.

Okta is a SAML identity provider (IdP), that can be easily set-up to do SSO to your AWS console. Okta does offer an [OSS java CLI]((https://github.com/oktadeveloper/okta-aws-cli-assume-role)) tool to obtain temporary AWS credentials, but we found it needs more information than the average Okta user would have and doesn't scale well if you have more than one Okta App.

With gimme-aws-creds all you need to know is your username, password, Okta url and MFA token, if MFA is enabled. gimme-aws-creds gives you the option to select which Okta AWS application and role you want credentials for.

## Prerequisites

[Okta SAML integration to AWS using the AWS App](https://help.okta.com/en/prod/Content/Topics/Miscellaneous/References/OktaAWSMulti-AccountConfigurationGuide.pdf)

Python 3.7+

## Installation

This is a Python 3 project.

Install/Upgrade from PyPi:

```bash
pip3 install --upgrade gimme-aws-creds
```

Full usage guide is available at the [project page](https://github.com/Nike-Inc/gimme-aws-creds)
