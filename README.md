# Gimme AWS Creds

[![][license img]][license]
[![][cicd img]][cicd]

gimme-aws-creds is a CLI that utilizes an [Okta](https://www.okta.com/) IdP via SAML to acquire temporary AWS credentials via AWS STS.

Okta is a SAML identity provider (IdP), that can be easily set-up to do SSO to your AWS console. Okta does offer an [OSS java CLI]((https://github.com/oktadeveloper/okta-aws-cli-assume-role)) tool to obtain temporary AWS credentials, but I found it needs more information than the average Okta user would have and doesn't scale well if have more than one Okta App.

With gimme-aws-creds all you need to know is your username, password, Okta url and MFA token, if MFA is enabled. gimme-aws-creds gives you the option to select which Okta AWS application and role you want credentials for. Alternatively, you can pre-configure the app and role name by passing -c or editing the config file. This is all covered in the usage section.

## Disclaimer
Okta is a registered trademark of Okta, Inc. and this tool has no affiliation with or sponsorship by Okta, Inc.

## Prerequisites

[Okta SAML integration to AWS using the AWS App](https://help.okta.com/en/prod/Content/Topics/Miscellaneous/References/OktaAWSMulti-AccountConfigurationGuide.pdf)

Python 3.7+

### Optional

[Gimme-creds-lambda](https://github.com/Nike-Inc/gimme-aws-creds/tree/master/lambda) can be used as a proxy to the Okta APIs needed by gimme-aws-creds.  This removes the requirement of an Okta API key.  Gimme-aws-creds authenticates to gimme-creds-lambda using OpenID Connect and the lambda handles all interactions with the Okta APIs.  Alternately, you can set the `OKTA_API_KEY` environment variable and the `gimme_creds_server` configuration value to 'internal' to call the Okta APIs directly from gimme-aws-creds.

## Installation

This is a Python 3 project.

Install/Upgrade from PyPi:

```bash
pip3 install --upgrade gimme-aws-creds
```

__OR__

Install/Upgrade the latest gimme-aws-creds package direct from GitHub:

```bash
pip3 install --upgrade git+git://github.com/Nike-Inc/gimme-aws-creds.git
```

__OR__

Install the gimme-aws-creds package if you have already cloned the source:

```bash
python3 setup.py install
```

__OR__

Use homebrew

```bash
brew install gimme-aws-creds
```

__OR__

Use with nix flakes
```bash
# flake.nix
# Use by running `nix develop`
{
  description = "Shell example";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  inputs.gimme-aws-creds.url = "github:Nike-Inc/gimme-aws-creds";

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    gimme-aws-creds,
    ...
  } @ inputs:
    flake-utils.lib.eachDefaultSystem
    (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        devShells.default = pkgs.mkShell {
          packages = [pkgs.bash gimme-aws-creds.defaultPackage.${system}];
        };
      }
    );
}
```

__OR__

Use with original nix
```bash
# shell.nix
# Use by running `nix-shell`
{pkgs ? import <nixpkgs> {}, ...}:
with pkgs; let
  gimme-src = fetchgit {
    name = "gimme-aws-creds";
    url = "https://github.com/Nike-Inc/gimme-aws-creds";
    branchName = "master";
    sha256 = "<replace>"; #nix-prefetch-url --unpack https://github.com/Nike-Inc/gimme-aws-creds/archive/master.tar.gz
  };

  gimme-aws-creds = import gimme-src;
in
  mkShell rec {
    name = "gimme-aws-creds";

    buildInputs = [
      bash
      (gimme-aws-creds.default)
    ];
  }
```

__OR__

Build the docker image locally:

```bash
docker build -t gimme-aws-creds .
```

To make it easier you can also create an alias for the gimme-aws-creds command with docker:

```bash
# make sure you have the "~/.okta_aws_login_config" locally first!
touch ~/.okta_aws_login_config && \
alias gimme-aws-creds="docker run -it --rm \
  -v ~/.aws/credentials:/root/.aws/credentials \
  -v ~/.okta_aws_login_config:/root/.okta_aws_login_config \
  gimme-aws-creds"
```

With this config, you will be able to run further commands seamlessly!

## Command Auto Completion

If you are using Bash or Zsh, you can add autocompletion for the gimme-aws-creds commandline options and profile names.  To add the autocomplete config, add the following to the end of your .bashrc or .zshrc:

.bashrc
```bash
INSTALL_DIR=$(dirname $(which gimme-aws-creds))
source ${INSTALL_DIR}/gimme-aws-creds-autocomplete.sh"
```

.zshrc
```bash
INSTALL_DIR=$(dirname $(which gimme-aws-creds))
autoload bashcompinit
bashcompinit
source ${INSTALL_DIR}/gimme-aws-creds-autocomplete.sh
```

## Using gimme-aws-creds with Okta Identity Engine

To use gimme-aws-creds with an Okta Identity Engine (OIE) domain, you must create a new OIDC Native Application and connect it to your AWS integration app(s).

The OIDC Native Application requires Grant Types `Authorization Code`, `Device Authorization` , and `Token Exchange`. These settings are in the Okta Admin UI at `Applications > [the OIDC app] > General Settings > Grant type`.

The pairing with the AWS Federation Application is achieved in the Fed app's Sign On Settings. These settings are in the Okta Admin UI at `Applications > [the AWS Fed app] > Sign On`. Make sure to set the `Allowed Web SSO Client` value to the Client ID of the OIDC Native Application. Repeat that setting for each AWS application you want to access with gimme-aws-creds.

Finally, set the Client ID in gimme-aws-creds (`gimme-aws-creds --action-configure` or update the `client_id` parameter in your config file)

**When using gimme-aws-creds with an OIE domain, you will authenticate using your browser.  Storing credentials in keychain or passing MFA codes through the command-line is NOT POSSIBLE.**

## Configuration

To set-up the configuration run:

```bash
gimme-aws-creds --action-configure
```

You can also set up different Okta configuration profiles, this is useful if you have multiple Okta accounts or environments you need credentials for. You can use the configuration wizard or run:

```bash
gimme-aws-creds --action-configure --profile profileName
```

A configuration wizard will prompt you to enter the necessary configuration parameters for the tool to run, the only one that is required is the `okta_org_url`. The configuration file is written to `~/.okta_aws_login_config`, but you can change the location with the environment variable `OKTA_CONFIG`.

- conf_profile - This sets the Okta configuration profile name, the default is DEFAULT.
- okta_org_url - This is your Okta organization url, which is typically something like `https://companyname.okta.com`.
- okta_auth_server - [Okta API Authorization Server](https://help.okta.com/en/prev/Content/Topics/Security/API_Access.htm) used for OpenID Connect authentication for gimme-creds-lambda
- client_id - OAuth client ID for user authentication in Okta Identity Engine and gimme-creds-lambda in Okta "classic"
- gimme_creds_server
  - URL for gimme-creds-lambda
  - 'internal' for direct interaction with the Okta APIs (`OKTA_API_KEY` environment variable required)
  - 'appurl' to set an aws application link url. This setting removes the need of an OKTA API key.
- write_aws_creds - True or False - If True, the AWS credentials will be written to `~/.aws/credentials` otherwise it will be written to stdout.
- cred_profile - If writing to the AWS cred file, this sets the name of the AWS credential profile.
  - The reserved word `role` will use the name component of the role arn as the profile name. i.e. arn:aws:iam::123456789012:role/okta-1234-role becomes section [okta-1234-role] in the aws credentials file
  - The reserved word `acc-role` will use the name component of the role arn prepended with account number (or alias if `resolve_aws_alias` is set to y) to avoid collisions, i.e. arn:aws:iam::123456789012:role/okta-1234-role becomes section [123456789012-okta-1234-role], or if `resolve_aws_alias` [<my alias>-okta-1234-role] in the aws credentials file
  - If set to `default` then the temp creds will be stored in the default profile
  - Note: if there are multiple roles, and `default` is selected it will be overwritten multiple times and last role wins. The same happens when `role` is selected and you have many accounts with the same role names. Consider using `acc-role` if this happens.
- aws_appname - This is optional. The Okta AWS App name, which has the role you want to assume.
- aws_rolename - This is optional. The ARN of the role you want temporary AWS credentials for.  The reserved word 'all' can be used to get and store credentials for every role the user is permissioned for.
- aws_default_duration = This is optional. Lifetime for temporary credentials, in seconds. Defaults to 1 hour (3600)
- app_url - If using 'appurl' setting for gimme_creds_server, this sets the url to the aws application configured in Okta. It is typically something like <https://something.okta[preview].com/home/amazon_aws/app_instance_id/something>
- okta_username - use this username to authenticate
- preferred_mfa_type - automatically select a particular  device when prompted for MFA:
  - push - Okta Verify App push or DUO push (depends on okta supplied provider type)
  - token:software:totp - OTP using the Okta Verify App
  - token:hardware - OTP using hardware like Yubikey
  - call - OTP via Voice call
  - sms - OTP via SMS message
  - web - DUO uses localhost webbrowser to support push|call|passcode
  - passcode - DUO uses `OKTA_MFA_CODE` or `--mfa-code` if set, or prompts user for passcode(OTP).
  
- resolve_aws_alias - y or n. If yes, gimme-aws-creds will try to resolve AWS account ids with respective alias names (default: n). This option can also be set interactively in the command line using `-r` or `--resolve` parameter
- include_path - (optional) Includes full role path to the role name in AWS credential profile name. (default: n).  If `y`: `<acct>-/some/path/administrator`. If `n`: `<acct>-administrator`
- remember_device - y or n. If yes, the MFA device will be remembered by Okta service for a limited time. This option can also be set interactively in the command line using `-m` or `--remember-device`
- output_format - `json` , `export` or `windows`, determines default credential output format, can be also specified by `--output-format FORMAT` and `-o FORMAT`.
- open-browser - Open the device authentication link in the default web browser automatically (Okta Identity Engine domains only)

## Configuration File

The config file follows a [configfile](https://docs.python.org/3/library/configparser.html) format.
By default, it is located in $HOME/.okta_aws_login_config

Example file:

```ini
[myprofile]
client_id = myclient_id
```

Configurations can inherit from other configurations to share common configuration parameters.

```ini
[my-base-profile]
client_id = myclient_id
[myprofile]
inherits = my-base-profile
aws_rolename = my-role
```

## Usage

**If you are not using gimme-creds-lambda nor using appurl settings, make sure you set the OKTA_API_KEY environment variable.**

After running --action-configure, just run gimme-aws-creds. You will be prompted for the necessary information.

```bash
$ ./gimme-aws-creds
Username: user@domain.com
Password for user@domain.com:
Authentication Success! Calling Gimme-Creds Server...
Pick an app:
[ 0 ] AWS Test Account
[ 1 ] AWS Prod Account
Selection: 1
Pick a role:
[ 0 ]: OktaAWSAdminRole
[ 1 ]: OktaAWSReadOnlyRole
Selection: 1
Multi-factor Authentication required.
Pick a factor:
[ 0 ] Okta Verify App: SmartPhone_IPhone: iPhone
[ 1 ] token:software:totp: user@domain.com
Selection: 0
Okta Verify push sent...
export AWS_ACCESS_KEY_ID=AQWERTYUIOP
export AWS_SECRET_ACCESS_KEY=T!#$JFLOJlsoddop1029405-P
```

You can automate the environment variable creation by running `$(gimme-aws-creds)` on linux or `gimme-aws-creds | iex` using Windows Powershell

You can run a specific configuration profile with the `--profile` parameter:

```bash
./gimme-aws-creds --profile profileName
```

The username and password you are prompted for are the ones you login to Okta with. You can predefine your username by setting the `OKTA_USERNAME` environment variable or using the `-u username` parameter.

If you have not configured an Okta App or Role, you will prompted to select one.

If all goes well you will get your temporary AWS access, secret key and token, these will either be written to stdout or `~/.aws/credentials`.

You can always run `gimme-aws-creds --help` for all the available options.

Alternatively, you can overwrite values in the config section with environment variables for instances where say you may want to change the duration of your token.
A list of values of to change with environment variables are:

- `AWS_DEFAULT_DURATION` - corresponds to `aws_default_duration` configuration
- `AWS_SHARED_CREDENTIALS_FILE` - file to write credentials to, points to `~/.aws/credentials` by default
- `GIMME_AWS_CREDS_CLIENT_ID` - corresponds to `client_id` configuration
- `GIMME_AWS_CREDS_CRED_PROFILE` - corresponds to `cred_profile` configuration
- `GIMME_AWS_CREDS_OUTPUT_FORMAT` - corresponds to `output_format` configuration and `--output-format` CLI option
- `OKTA_AUTH_SERVER` - corresponds to `okta_auth_server` configuration
- `OKTA_DEVICE_TOKEN` - corresponds to `device_token` configuration, can be used in CI
- `OKTA_MFA_CODE` - corresponds to `--mfa-code` CLI option
- `OKTA_PASSWORD` - provides password during authentication, can be used in CI
- `OKTA_USERNAME` - corresponds to `okta_username` configuration and `--username` CLI option

Example: `GIMME_AWS_CREDS_CLIENT_ID='foobar' AWS_DEFAULT_DURATION=12345 gimme-aws-creds`

For changing variables outside of this, you'd need to create a separate profile altogether with `gimme-aws-creds --action-configure --profile profileName`

### Viewing Profiles

`gimme-aws-creds --action-list-profiles` will go to your okta config file and print out all profiles created and their settings.

### Viewing roles

`gimme-aws-creds --action-list-roles` will print all available roles to STDOUT without retrieving their credentials.

### Credential expiration time

Writing to the AWS credentials file will include the `x_security_token_expires` value in RFC3339 format. This allows tools to validate if the credentials are expiring or are expiring soon and warn the user or trigger a refresh.

### Generate credentials as json

`gimme-aws-creds -o json` will print out credentials in JSON format - 1 entry per line

### Store credentials from json

`gimme-aws-creds --action-store-json-creds` will store JSON formatted credentials from `stdin` to
aws credentials file, eg: `gimme-aws-creds -o json | gimme-aws-creds --action-store-json-creds`.
Data can be modified by scripts on the way.

### Usage in python code

Configuration and interactions can be configured using [`gimme_aws_creds.ui`](./gimme_aws_creds/ui.py),
UserInterfaces support all kind of interactions within library including: asking for input, `sys.argv` and `os.environ`
overrides.

```python
import sys
import gimme_aws_creds.main
import gimme_aws_creds.ui

account_ids = sys.argv[1:] or [
  '123456789012',
  '120123456789',
]

pattern = "|".join(sorted(set(account_ids)))
pattern = '/:({}):/'.format(pattern)
ui = gimme_aws_creds.ui.CLIUserInterface(argv=[sys.argv[0], '--roles', pattern])
creds = gimme_aws_creds.main.GimmeAWSCreds(ui=ui)

# Print out all selected roles:
for role in creds.aws_selected_roles:
    print(role)

# Generate credentials overriding profile name with `okta-<account_id>`
for data in creds.iter_selected_aws_credentials():
    arn = data['role']['arn']
    account_id = None
    for piece in arn.split(':'):
        if len(piece) == 12 and piece.isdigit():
            account_id = piece
            break
  
    if account_id is None:
        raise ValueError("Didn't find aws_account_id (12 digits) in {}".format(arn))

    data['profile']['name'] = 'okta-{}'.format(account_id)
    creds.write_aws_creds_from_data(data)

```

## MFA security keys support

gimme-aws-creds works both on FIDO1 enabled org and WebAuthN enabled org

Note that FIDO1 will probably be deprecated in the near future as standards moves forward to WebAuthN

WebAuthN support is available for usb security keys (gimme-aws-creds relies on the yubico fido2 lib).
 
To use your local machine as an authenticator, along with Touch ID or Windows Hello, if available,
you must register a new authenticator via gimme-aws-creds, using:
```bash
gimme-aws-creds --action-setup-fido-authenticator
```

Then, you can choose the newly registered authenticator from the factors list.

## Running Tests

You can run all the unit tests using pytest. Most of the tests are mocked.

```bash
pytest -vv tests
```

## Maintenance

This project is maintained by [Eric Pierce](https://github.com/epierce)

## Thanks and Credit

I came across [okta_aws_login](https://github.com/nimbusscale/okta_aws_login) written by Joe Keegan, when I was searching for a CLI tool that generates AWS tokens via Okta. Unfortunately it hasn't been updated since 2015 and didn't seem to work with the current Okta version. But there was still some great code I was able to reuse under the MIT license for gimme-aws-creds. I have noted in the comments where I used his code, to make sure he receives proper credit.

## Etc

[okta-aws-cli](https://github.com/okta/okta-aws-cli)

[okta-aws-cli-assume-role](https://github.com/oktadev/okta-aws-cli-assume-role)

[AWS - How to Implement Federated API and CLI Access Using SAML 2.0 and AD FS](https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/)

## [Contributing](https://github.com/Nike-Inc/gimme-aws-creds/blob/master/CONTRIBUTING.md)

## License

Gimme AWS Creds is released under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0)

[license]:LICENSE
[license img]:https://img.shields.io/badge/License-Apache%202-blue.svg
[cicd]:https://github.com/Nike-Inc/gimme-aws-creds/actions/workflows/cicd.yml
[cicd img]:https://github.com/Nike-Inc/gimme-aws-creds/actions/workflows/cicd.yml/badge.svg
