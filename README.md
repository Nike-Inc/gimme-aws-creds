# Gimme AWS Creds

[![][license img]][license]
[![][cicd img]][cicd]

`gimme-aws-creds` is a CLI that uses an [Okta](https://www.okta.com/) IdP via SAML to acquire short-lived cloud credentials. It supports:

- **AWS** - temporary credentials via AWS STS `AssumeRoleWithSAML`.
- **Alibaba Cloud** - temporary RAM credentials via Alibaba Cloud STS `AssumeRoleWithSAML`, using the same Okta authentication flow. See [Alibaba Cloud](#alibaba-cloud).

All you need is your Okta username, password, org URL, and an MFA factor (if MFA is enabled). gimme-aws-creds prompts you to pick the Okta application and role, or you can pre-configure them per profile.

Okta does offer an [OSS Java CLI](https://github.com/oktadeveloper/okta-aws-cli-assume-role) for the same purpose, but it requires more configuration than the average Okta user has and doesn't scale well across multiple Okta apps. gimme-aws-creds is designed to be friendlier for everyday use.

## Disclaimer
Okta is a registered trademark of Okta, Inc. and this tool has no affiliation with or sponsorship by Okta, Inc.

## Table of Contents

- [Gimme AWS Creds](#gimme-aws-creds)
  - [Disclaimer](#disclaimer)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
    - [Recommended](#recommended)
    - [Other Installation Methods](#other-installation-methods)
  - [Command Auto Completion](#command-auto-completion)
  - [Okta Setup](#okta-setup)
    - [Using gimme-aws-creds with Okta Identity Engine](#using-gimme-aws-creds-with-okta-identity-engine)
      - [Okta Identity Engine and Device Authorization Flow](#okta-identity-engine-and-device-authorization-flow)
    - [Forcing the use of the Okta Classic login flow](#forcing-the-use-of-the-okta-classic-login-flow)
    - [MFA Security Keys Support](#mfa-security-keys-support)
  - [Configuration](#configuration)
    - [Configuration File Format](#configuration-file-format)
    - [Configuration Parameters](#configuration-parameters)
      - [Preferred MFA Types](#preferred-mfa-types)
    - [`cred_profile` Reserved Words](#cred_profile-reserved-words)
  - [Environment Variables](#environment-variables)
  - [Usage](#usage)
    - [Viewing Profiles](#viewing-profiles)
    - [Viewing Roles](#viewing-roles)
    - [Credential Expiration Time](#credential-expiration-time)
    - [Generate Credentials as JSON](#generate-credentials-as-json)
    - [Store Credentials from JSON](#store-credentials-from-json)
  - [Python API](#python-api)
  - [Cloud Provider Support](#cloud-provider-support)
    - [AWS](#aws)
    - [Alibaba Cloud](#alibaba-cloud)
      - [Prerequisites](#prerequisites-1)
      - [Setup](#setup)
      - [Usage](#usage-1)
      - [Output](#output)
      - [Limitations](#limitations)
  - [Troubleshooting](#troubleshooting)
  - [Platform Notes](#platform-notes)
    - [Windows](#windows)
  - [Running Tests](#running-tests)
  - [Project](#project)
    - [Maintenance](#maintenance)
    - [Thanks and Credit](#thanks-and-credit)
    - [Related Projects](#related-projects)
    - [Contributing](#contributing)
    - [License](#license)

## Quick Start

```bash
# 1. Install
pip3 install --upgrade gimme-aws-creds

# 2. Configure a profile (will prompt for Okta org URL, app, role, etc.)
gimme-aws-creds --action-configure

# 3. Get credentials
gimme-aws-creds
```

For Alibaba Cloud RAM credentials, install the optional extra and pass `--enable-alicloud` during configuration:

```bash
pip3 install --upgrade "gimme-aws-creds[alicloud]"
gimme-aws-creds --action-configure --enable-alicloud --profile alicloud
```

See [Configuration](#configuration) and [Usage](#usage) for full details, or [Cloud Provider Support](#cloud-provider-support) for cloud-specific notes.

## Prerequisites

- **Python 3.10+**
- **Okta SAML integration to AWS** using the [AWS App](https://help.okta.com/en-us/content/topics/deploymentguides/aws/aws-configure-identity-provider.htm).
- **(Optional) [gimme-creds-lambda](https://github.com/Nike-Inc/gimme-aws-creds/tree/master/lambda)** as a proxy to the Okta APIs needed by gimme-aws-creds. This removes the requirement of an Okta API key. gimme-aws-creds authenticates to gimme-creds-lambda using OpenID Connect and the lambda handles all interactions with the Okta APIs. Alternately, set the `OKTA_API_KEY` environment variable and the `gimme_creds_server` configuration value to `internal` to call the Okta APIs directly.
- **(Optional) Alibaba Cloud SDK extras** if you plan to retrieve Alibaba Cloud RAM credentials: `pip install "gimme-aws-creds[alicloud]"`. See [Alibaba Cloud](#alibaba-cloud).

> See [Platform Notes](#platform-notes) for known platform-specific caveats (e.g. Python 3.10+ on Windows).

## Installation

### Recommended

Install or upgrade from PyPI:

```bash
pip3 install --upgrade gimme-aws-creds
```

Or use Homebrew (macOS):

```bash
brew install gimme-aws-creds
```

### Other Installation Methods

<details>
<summary>Install from GitHub</summary>

```bash
pip3 install --upgrade git+git://github.com/Nike-Inc/gimme-aws-creds.git
```

</details>

<details>
<summary>Install from local source</summary>

```bash
python -m pip install .
```

</details>

<details>
<summary>Nix flakes</summary>

```nix
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

</details>

<details>
<summary>Original Nix (shell.nix)</summary>

```nix
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

</details>

<details>
<summary>Docker</summary>

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

With this config, you will be able to run further commands seamlessly.

</details>

## Command Auto Completion

If you are using Bash or Zsh, you can add autocompletion for the gimme-aws-creds commandline options and profile names. Add the following to the end of your `.bashrc` or `.zshrc`:

`.bashrc`:

```bash
INSTALL_DIR=$(dirname $(which gimme-aws-creds))
source ${INSTALL_DIR}/gimme-aws-creds-autocomplete.sh
```

`.zshrc`:

```bash
INSTALL_DIR=$(dirname $(which gimme-aws-creds))
autoload bashcompinit
bashcompinit
source ${INSTALL_DIR}/gimme-aws-creds-autocomplete.sh
```

## Okta Setup

### Using gimme-aws-creds with Okta Identity Engine

There are two options for using gimme-aws-creds with an Okta Identity Engine (OIE) domain:

- [Device Authorization Flow](#okta-identity-engine-and-device-authorization-flow) (recommended)
- [Forcing the use of the Okta Classic login flow](#forcing-the-use-of-the-okta-classic-login-flow)

#### Okta Identity Engine and Device Authorization Flow

This is the recommended method for authentication with OIE. It matches the flow used by Okta's [AWS client](https://github.com/okta/okta-aws-cli). When using gimme-aws-creds with the Device Authorization flow, you will authenticate using your browser. Storing credentials in keychain or passing MFA codes through the command line is **NOT POSSIBLE**.

To use gimme-aws-creds with an OIE domain, you must create a new OIDC Native Application and connect it to your AWS integration app(s):

1. The OIDC Native Application requires Grant Types `Authorization Code`, `Device Authorization`, and `Token Exchange`. These settings are in the Okta Admin UI at `Applications > [the OIDC app] > General Settings > Grant type`.
2. Pair the OIDC app with each AWS Federation Application: in `Applications > [the AWS Fed app] > Sign On`, set `Allowed Web SSO Client` to the Client ID of the OIDC Native Application. Repeat for each AWS application you want to access with gimme-aws-creds.
3. Set the Client ID in gimme-aws-creds (`gimme-aws-creds --action-configure` or update the `client_id` parameter in your config file).

> Make sure to use the same authentication policy for both the AWS Federation Application and the OIDC application (or at least equivalent policy rules). If not, you'll receive an error when requesting the Web SSO token.

### Forcing the use of the Okta Classic login flow

The login flow used in Okta Classic currently still works with Okta Identity Engine domains, but with these caveats:

- The Okta classic flow passes the `stateToken` parameter when requesting "step-up" authentication. This capability was removed in OIE, so if the authentication policy on your AWS app(s) requires MFA but the Global Session Policy does not (or if a higher level of MFA factor is required to access AWS), you cannot authenticate using the classic login flow.
- MFA using Okta Verify is only supported on mobile devices. Okta Verify on macOS/Windows is not supported.
- Passwordless authentication and endpoint security checks are not supported.

### MFA Security Keys Support

gimme-aws-creds works with both FIDO1-enabled and WebAuthN-enabled Okta orgs.

> Note: FIDO1 will probably be deprecated in the near future as standards move to WebAuthN.

WebAuthN support is available for USB security keys (gimme-aws-creds relies on the Yubico fido2 lib).

To use your local machine as an authenticator (along with Touch ID or Windows Hello, if available), register a new authenticator via gimme-aws-creds:

```bash
gimme-aws-creds --action-setup-fido-authenticator
```

You can then choose the newly registered authenticator from the factors list.

## Configuration

To set up the configuration, run:

```bash
gimme-aws-creds --action-configure
```

You can also set up different Okta configuration profiles, which is useful if you have multiple Okta accounts or environments you need credentials for:

```bash
gimme-aws-creds --action-configure --profile profileName
```

The wizard prompts you to enter the necessary configuration parameters; the only one that is required is `okta_org_url`. The configuration file is written to `~/.okta_aws_login_config` (override with the `OKTA_CONFIG` environment variable).

### Configuration File Format

The config file follows a [configfile](https://docs.python.org/3/library/configparser.html) format. By default, it is located at `$HOME/.okta_aws_login_config`.

Example file:

```ini
[myprofile]
client_id = myclient_id
```

Configurations can inherit from other configurations to share common parameters:

```ini
[my-base-profile]
client_id = myclient_id

[myprofile]
inherits = my-base-profile
aws_rolename = my-role
```

### Configuration Parameters

| Key | Description |
| --- | --- |
| `conf_profile` | Okta configuration profile name. Default: `DEFAULT`. |
| `okta_org_url` | Your Okta organization URL, typically `https://companyname.okta.com`. |
| `okta_auth_server` | [Okta API Authorization Server](https://help.okta.com/en/prev/Content/Topics/Security/API_Access.htm) used for OpenID Connect authentication for gimme-creds-lambda. |
| `client_id` | OAuth client ID for user authentication in Okta Identity Engine and gimme-creds-lambda in Okta Classic. |
| `gimme_creds_server` | One of: a gimme-creds-lambda URL; `internal` for direct Okta API calls (`OKTA_API_KEY` env var required); `appurl` to use an AWS app link URL (no Okta API key required). |
| `write_aws_creds` | `True` or `False`. If `True`, credentials are written to `~/.aws/credentials` (or `~/.aliyun/config.json` for Alibaba Cloud); otherwise to stdout. |
| `cred_profile` | Name of the AWS credential profile when writing to the credentials file. Supports reserved words; see [`cred_profile` Reserved Words](#cred_profile-reserved-words). Override with `--aws-cred-profile` or `GIMME_AWS_CREDS_CRED_PROFILE`. |
| `aws_appname` | (Optional) Okta AWS App name containing the role you want to assume. |
| `aws_rolename` | (Optional) ARN of the role to assume. The reserved word `all` retrieves credentials for every role the user is permissioned for. |
| `aws_default_duration` | (Optional) Lifetime for temporary credentials, in seconds. Default: `3600`. |
| `app_url` | When using `gimme_creds_server = appurl`, the URL of the AWS application configured in Okta. Typically `https://something.okta[preview].com/home/amazon_aws/app_instance_id/something`. |
| `okta_username` | Username to authenticate with. |
| `enable_keychain` | Enable use of the system keychain to store the user's password. |
| `preferred_mfa_type` | Automatically select an MFA device. See [MFA factor types](#preferred-mfa-types). |
| `preferred_mfa_provider` | (Optional) Automatically select an MFA provider: `GOOGLE`, `OKTA`, or `DUO`. |
| `duo_universal_factor` | (Optional, case-sensitive) Duo Universal Prompt factor: `Duo Push` (default), `Passcode`, `Phone Call`. |
| `resolve_aws_alias` | `y` or `n`. If `y`, resolve AWS account IDs to alias names (default `n`). Also settable via `-r` / `--resolve`. |
| `include_path` | (Optional) Include full role path in the AWS credential profile name (default `n`). If `y`: `<acct>-/some/path/administrator`. If `n`: `<acct>-administrator`. |
| `remember_device` | `y` or `n`. If `y`, the MFA device will be remembered by Okta for a limited time. Also settable via `-m` / `--remember-device`. |
| `output_format` | `json`, `export`, or `windows`. Determines the default credential output format. Override with `--output-format` / `-o`. The `export` and `windows` formats produce the correct env var names for both AWS and Alibaba Cloud. |
| `open_browser` | Open the device authentication link in the default web browser automatically (OIE only). |
| `force_classic` | Force the use of the Okta Classic login process (OIE only). |
| `enable_alicloud` | `y` or `n`. If `y`, enable Alibaba Cloud RAM support for this profile (OIE only). Requires `pip install "gimme-aws-creds[alicloud]"`. Also settable via `--enable-alicloud` or `GIMME_AWS_CREDS_ENABLE_ALICLOUD`. See [Alibaba Cloud](#alibaba-cloud). |
| `alicloud_saml_url` | (Optional, Alibaba Cloud only) Explicit SAML SSO URL for the Alibaba Cloud app in Okta. Falls back to the app link if not set. |
| `alicloud_region` | (Optional, Alibaba Cloud only) Alibaba Cloud STS region used for `AssumeRoleWithSAML`. Default: `cn-hangzhou`. |

#### Preferred MFA Types

Values for `preferred_mfa_type`:

- `push` - Okta Verify App push or DUO push (depends on Okta-supplied provider type)
- `token:software:totp` - OTP using the Okta Verify App
- `token:hardware` - OTP using hardware like YubiKey
- `call` - OTP via voice call
- `sms` - OTP via SMS message
- `email` - OTP via email
- `web` - DUO uses a localhost web browser to support push/call/passcode
- `passcode` - DUO uses `OKTA_MFA_CODE` or `--mfa-code` if set, or prompts the user for a passcode (OTP)
- `claims_provider` - DUO Universal Prompt

### `cred_profile` Reserved Words

When writing credentials to `~/.aws/credentials`, `cred_profile` accepts these reserved words:

- **`role`** - Use the name component of the role ARN as the profile name.
  Example: `arn:aws:iam::123456789012:role/okta-1234-role` → `[okta-1234-role]`
- **`acc`** - Use the account number (or alias if `resolve_aws_alias = y`) as the profile name.
  Example: `arn:aws:iam::123456789012:role/okta-1234-role` → `[arn:aws:iam::123456789012]`, or `[okta-1234-role]` if `resolve_aws_alias` is set.
- **`acc-role`** - Account number (or alias) prepended to the role name to avoid collisions.
  Example: `arn:aws:iam::123456789012:role/okta-1234-role` → `[123456789012-okta-1234-role]`, or `[okta-1234-role]` if `resolve_aws_alias` is set.
- **`default`** - Store the temp creds in the default profile.

> Note: if there are multiple roles and `default` is selected, the profile is overwritten multiple times and the last role wins. The same happens with `role` if you have many accounts with the same role names. Consider using `acc-role` if this happens.

## Environment Variables

You can override values from the config section with environment variables. This is useful for one-off changes (e.g. token duration) without creating a new profile.

| Variable | Description |
| --- | --- |
| `AWS_DEFAULT_DURATION` | Corresponds to `aws_default_duration`. |
| `AWS_SHARED_CREDENTIALS_FILE` | File to write AWS credentials to. Defaults to `~/.aws/credentials`. |
| `AWS_STS_REGION` | Force the use of AWS STS in a specific region (`us-east-1`, `eu-north-1`, etc.). |
| `GIMME_AWS_CREDS_CLIENT_ID` | Corresponds to `client_id`. |
| `GIMME_AWS_CREDS_CRED_PROFILE` | Corresponds to `cred_profile` and `--aws-cred-profile`. |
| `GIMME_AWS_CREDS_OUTPUT_FORMAT` | Corresponds to `output_format` and `--output-format`. |
| `GIMME_AWS_CREDS_ENABLE_ALICLOUD` | Corresponds to `enable_alicloud` and `--enable-alicloud`. |
| `OKTA_API_KEY` | Required if `gimme_creds_server = internal`. |
| `OKTA_AUTH_SERVER` | Corresponds to `okta_auth_server`. |
| `OKTA_CONFIG` | Override location of the gimme-aws-creds config file (default `~/.okta_aws_login_config`). |
| `OKTA_DEVICE_TOKEN` | Corresponds to `device_token`; useful in CI. |
| `OKTA_MFA_CODE` | Corresponds to `--mfa-code`. |
| `OKTA_PASSWORD` | Provides password during authentication; useful in CI. |
| `OKTA_USERNAME` | Corresponds to `okta_username` and `--username`. |
| `ALIBABA_CLOUD_SHARED_CREDENTIALS_FILE` | Override the path to the Alibaba Cloud credentials file (default `~/.aliyun/config.json`). |

Example:

```bash
GIMME_AWS_CREDS_CLIENT_ID='foobar' AWS_DEFAULT_DURATION=12345 gimme-aws-creds
```

For changes outside of these variables, create a separate profile with `gimme-aws-creds --action-configure --profile profileName`.

## Usage

> **If you are not using gimme-creds-lambda nor `appurl` settings, make sure you set the `OKTA_API_KEY` environment variable.**

After running `--action-configure`, run `gimme-aws-creds`. You'll be prompted for the necessary information.

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

Automate the environment variable creation by running `$(gimme-aws-creds)` on Linux/macOS or `gimme-aws-creds | iex` in Windows PowerShell.

Run a specific configuration profile with `--profile`:

```bash
./gimme-aws-creds --profile profileName
```

The username and password you are prompted for are the ones you log in to Okta with. You can predefine your username via the `OKTA_USERNAME` environment variable or the `-u username` parameter.

If you have not configured an Okta App or Role, you will be prompted to select one.

If all goes well, you will get your temporary credentials, written to either stdout or `~/.aws/credentials` (or `~/.aliyun/config.json` for Alibaba Cloud).

Run `gimme-aws-creds --help` for all available options.

### Viewing Profiles

`gimme-aws-creds --action-list-profiles` reads your Okta config file and prints all profiles created and their settings.

### Viewing Roles

`gimme-aws-creds --action-list-roles` prints all available roles to stdout without retrieving credentials.

### Credential Expiration Time

Writing to the AWS credentials file includes the `x_security_token_expires` value in RFC3339 format. Tools can use this to detect credentials that are expiring (or expired) and warn the user or trigger a refresh.

### Generate Credentials as JSON

`gimme-aws-creds -o json` prints credentials in JSON format - one entry per line.

### Store Credentials from JSON

`gimme-aws-creds --action-store-json-creds` stores JSON-formatted credentials read from `stdin` into the AWS credentials file. Example:

```bash
gimme-aws-creds -o json | gimme-aws-creds --action-store-json-creds
```

Data can be modified by scripts in between.

## Python API

Configuration and interactions can be controlled programmatically via [`gimme_aws_creds.ui`](./gimme_aws_creds/ui.py). `UserInterface` implementations support all kinds of interactions including: asking for input, `sys.argv` and `os.environ` overrides.

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

# Generate credentials, overriding profile name with `okta-<account_id>`
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

## Cloud Provider Support

gimme-aws-creds supports two cloud providers, selected per profile.

### AWS

This is the default mode. gimme-aws-creds parses AWS IAM role ARNs (`arn:aws:iam::<account>:role/<name>`) from the SAML assertion and calls AWS STS [`AssumeRoleWithSAML`](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithSAML.html) to obtain temporary credentials. Both standard AWS, AWS GovCloud, and AWS China partitions are recognized from the SAML ACS URL.

Output is written to `~/.aws/credentials` (or stdout) using the standard `aws_access_key_id` / `aws_secret_access_key` / `aws_session_token` keys.

### Alibaba Cloud

gimme-aws-creds can retrieve temporary Alibaba Cloud RAM credentials using the same Okta authentication flow. It performs an Okta Identity Engine [Native-to-Web SSO interclient token exchange](https://developer.okta.com/docs/guides/native-to-web-sso/main/) to obtain a SAML assertion for your Alibaba Cloud app, then calls Alibaba Cloud STS [`AssumeRoleWithSAML`](https://www.alibabacloud.com/help/en/ram/developer-reference/api-sts-2015-04-01-assumerolewithsaml) to mint short-lived RAM credentials.

> Naming note: Alibaba Cloud is informally referred to as "AliCloud" in flag and config option names (e.g. `--enable-alicloud`, `enable_alicloud`).

#### Prerequisites

1. **Okta Identity Engine** - Alibaba Cloud support requires the OIE Device Authorization flow. The Okta Classic flow is not supported.
2. **Optional Alibaba Cloud SDK** - Install the optional dependency group:
   ```bash
   pip install "gimme-aws-creds[alicloud]"
   ```
   Without this extra, gimme-aws-creds will refuse to enable Alibaba Cloud and report a clear error pointing to the install command.
3. **Okta application configuration** - In your Okta org, configure:
   - An Alibaba Cloud SAML app with the appropriate Alibaba Cloud RAM role mappings.
   - The OIDC Native Application's `Allowed Web SSO Client` setting to permit Web SSO into the Alibaba Cloud SAML app (the same pairing pattern used for AWS Federation Apps; see [Using gimme-aws-creds with Okta Identity Engine](#using-gimme-aws-creds-with-okta-identity-engine)).
   - Native-to-Web SSO / interclient token exchange enabled for that pair.

#### Setup

Enable Alibaba Cloud support when configuring a profile:

```bash
gimme-aws-creds --action-configure --enable-alicloud --profile alicloud-profile
```

The configuration wizard will prompt you for the Alibaba Cloud SAML SSO URL. You can also edit `~/.okta_aws_login_config` directly:

```ini
[alicloud-profile]
okta_org_url = https://companyname.okta.com
okta_auth_server = your_auth_server
gimme_creds_server = appurl
app_url = https://companyname.okta.com/app/china_alibabacloud/app_instance_id/embed_url
client_id = your_client_id
enable_alicloud = True
alicloud_saml_url = https://companyname.okta.com/app/china_alibabacloud/app_instance_id/sso/saml
alicloud_region = cn-hangzhou
```

Alibaba Cloud-specific configuration keys:

| Key | Description |
| --- | --- |
| `enable_alicloud` | `y`/`n` (or `True`/`False`). Switches the profile from AWS STS to Alibaba Cloud STS. Also settable via `--enable-alicloud` or `GIMME_AWS_CREDS_ENABLE_ALICLOUD`. |
| `alicloud_saml_url` | Explicit SAML SSO URL for the Alibaba Cloud app in Okta. Falls back to the app link if not set. |
| `alicloud_region` | Alibaba Cloud STS region used for `AssumeRoleWithSAML`. Default: `cn-hangzhou`. |

#### Usage

Once a profile is configured, run gimme-aws-creds the usual way:

```bash
gimme-aws-creds --profile alicloud-profile
```

Role discovery, MFA, and the `--roles` filter all behave the same as for AWS - gimme-aws-creds simply parses Alibaba Cloud RAM role ARNs (`acs:ram::<account_id>:role/<role_name>`) from the SAML assertion instead of AWS IAM ARNs.

#### Output

The `export` and `windows` output formats emit the standard Alibaba Cloud SDK environment variables:

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=...
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
export ALIBABA_CLOUD_SECURITY_TOKEN=...
```

When `write_aws_creds` is enabled, credentials are written to `~/.aliyun/config.json` in the JSON profile format used by the official [`aliyun` CLI](https://github.com/aliyun/aliyun-cli) (`mode: StsToken`). Each gimme-aws-creds profile is added or updated as a named entry under `profiles`, and `current` is set to the most recently written profile. The `x_security_token_expires` field is included so external tools can detect expiring credentials.

The credentials file location can be overridden with the `ALIBABA_CLOUD_SHARED_CREDENTIALS_FILE` environment variable.

#### Limitations

- Alibaba Cloud STS caps `AssumeRoleWithSAML` sessions at 3600 seconds (1 hour). Larger values for `aws_default_duration` are clamped down to 3600 for Alibaba Cloud profiles.
- Mixing AWS and Alibaba Cloud roles in a single invocation is not supported - a profile is either AWS-mode or Alibaba Cloud-mode based on `enable_alicloud`.

## Troubleshooting

**`400 Bad Request` when requesting the Web SSO token (OIE)**
The authentication policies on the OIDC Native Application and the AWS/Alibaba Cloud Federation Application are not equivalent. Make sure both apps use the same authentication policy (or equivalent rules) - see [OIE setup](#using-gimme-aws-creds-with-okta-identity-engine).

**`Alibaba Cloud is enabled but optional SDK packages are not installed`**
You set `enable_alicloud = True` (or passed `--enable-alicloud`) but did not install the optional extra. Run:
```bash
pip install "gimme-aws-creds[alicloud]"
```

**Alibaba Cloud session ends after 1 hour even though `aws_default_duration` is larger**
This is a hard cap from Alibaba Cloud STS - `AssumeRoleWithSAML` sessions are limited to 3600 seconds. gimme-aws-creds clamps the requested duration accordingly.

**WebAuthn does not work on Windows with Python 3.10+**
This is a known compatibility issue. See [Platform Notes](#platform-notes).

**Okta Verify on macOS/Windows is not detected (Classic flow)**
Okta Verify on desktop is not supported by the Classic login flow. Use a mobile Okta Verify factor, or switch to the OIE Device Authorization flow.

**Multiple credentials with the same name overwrite each other**
You're using `cred_profile = role` (or `default`) with multiple accounts that have the same role name. Switch to `cred_profile = acc-role` to disambiguate. See [`cred_profile` Reserved Words](#cred_profile-reserved-words).

## Platform Notes

### Windows

`gimme-aws-creds` depends on the [ctap-keyring-device](https://pypi.org/project/ctap-keyring-device/) library for WebAuthn support. All released versions of `ctap-keyring-device` require [winRT](https://pypi.org/project/winrt/) on Windows, which only works on Python 3.9 and lower and is no longer maintained. Until a version of `ctap-keyring-device` that supports `winSDK` (the replacement for winRT) is released to PyPI (or some other solution is found) WebAuthn support will not be available on Python 3.10+ on Windows.

## Running Tests

You can run all the unit tests using pytest. Most of the tests are mocked.

```bash
pytest -vv tests
```

To run with coverage reporting:

```bash
pytest --cov=gimme_aws_creds tests/
```

## Project

### Maintenance

This project is maintained by [Eric Pierce](https://github.com/epierce).

### Thanks and Credit

I came across [okta_aws_login](https://github.com/nimbusscale/okta_aws_login) by Joe Keegan when I was searching for a CLI tool that generates AWS tokens via Okta. Unfortunately it hadn't been updated since 2015 and didn't seem to work with the current Okta version, but there was still some great code I was able to reuse under the MIT license for gimme-aws-creds. I have noted in the comments where I used his code, to make sure he receives proper credit.

### Related Projects

- [okta-aws-cli](https://github.com/okta/okta-aws-cli)
- [okta-aws-cli-assume-role](https://github.com/oktadev/okta-aws-cli-assume-role)
- [AWS - How to Implement Federated API and CLI Access Using SAML 2.0 and AD FS](https://aws.amazon.com/blogs/security/how-to-implement-federated-api-and-cli-access-using-saml-2-0-and-ad-fs/)

### Contributing

See [CONTRIBUTING.md](https://github.com/Nike-Inc/gimme-aws-creds/blob/master/CONTRIBUTING.md).

### License

Gimme AWS Creds is released under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

[license]:LICENSE
[license img]:https://img.shields.io/badge/License-Apache%202-blue.svg
[cicd]:https://github.com/Nike-Inc/gimme-aws-creds/actions/workflows/cicd.yml
[cicd img]:https://github.com/Nike-Inc/gimme-aws-creds/actions/workflows/cicd.yml/badge.svg
