# gimme-aws-creds - Project Overview

## Executive Summary

**gimme-aws-creds** is a Python CLI tool that acquires temporary AWS credentials via AWS STS using Okta as a SAML Identity Provider (IdP). It supports both Okta Classic and Okta Identity Engine authentication flows with comprehensive MFA support, and can also retrieve Alibaba Cloud RAM credentials via the same Okta authentication flow.

## Project Metadata

| Property | Value |
|----------|-------|
| **Name** | gimme-aws-creds |
| **Released Version** | 2.8.2 |
| **Latest Version** | 2.9.0-pre |
| **License** | Apache License 2.0 |
| **Python** | 3.10+ |
| **Maintainer** | Eric Pierce |
| **Repository** | https://github.com/Nike-Inc/gimme-aws-creds |

## Purpose & Problem Solved

Organizations using Okta for SSO to AWS need a way to obtain temporary AWS credentials for CLI/API access. gimme-aws-creds solves this by:

1. Authenticating users via Okta (Classic or Identity Engine)
2. Handling multi-factor authentication (MFA) flows
3. Retrieving SAML assertions from Okta
4. Exchanging SAML assertions for AWS STS (or Alibaba Cloud RAM) temporary credentials
5. Writing credentials to `~/.aws/credentials` (or `~/.aliyun/config.json`) or outputting to stdout

## Key Features

- **Dual Okta Platform Support**: Works with both Okta Classic and Okta Identity Engine domains
- **Comprehensive MFA**: Push, TOTP, SMS, Email, Voice Call, DUO (iframe + Universal Prompt), WebAuthn, U2F, hardware tokens
- **Multi-Cloud Output**: AWS STS (standard, GovCloud, China partitions) and Alibaba Cloud RAM
- **Multiple Output Formats**: Shell exports (`export`), JSON, Windows PowerShell (`windows`)
- **Profile Management**: Multiple configuration profiles with inheritance via `inherits = parent_profile`
- **AWS Account Resolution**: Resolves account IDs to friendly aliases by scraping the AWS sign-in page
- **Credential Storage**: Automatic storage in AWS credentials file with `x_security_token_expires` (RFC3339) for expiration tracking
- **Lambda Integration**: Optional [gimme-creds-lambda](https://github.com/Nike-Inc/gimme-aws-creds/tree/master/lambda) proxy for API key-less operation
- **Debug & Diagnostics**: `--debug` produces structured request/response logs and a "Resolved Configuration" report (with source attribution: CLI / env / profile / default), with automatic redaction of sensitive payloads (SAML responses, OAuth tokens, passwords, authorization headers)
- **Source-Attribution Tracking**: `Config` records, per value, whether it came from a CLI flag, environment variable, profile setting, inherited profile, or default

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| **Language** | Python | `3.10+` |
| **AWS SDK** | boto3 | `>=1.42.24,<2.0.0` |
| **HTTP** | requests | `>=2.31.0,<3.0.0` |
| **HTTP transport** | urllib3 | `>=2.6.3,<3.0.0` |
| **HTML Parsing** | beautifulsoup4 | `>=4.14.3,<5.0.0` |
| **HTML5** | html5lib | `>=1.1,<2.0.0` |
| **Okta SDK** | okta | `>=2.9.13,<3.0.0` |
| **FIDO2/WebAuthn** | fido2 | `>=0.9.1,<0.10.0` |
| **CTAP keyring (FIDO via system keychain)** | ctap-keyring-device | `==1.0.6` (non-Win or Python <3.10 on Windows) |
| **JWT** | pyjwt | `>=2.10.1,<3.0.0` |
| **Keyring** | keyring | `>=25.6.0,<26.0.0` |
| **URL Parsing** | furl | `>=2.1.4,<3.0.0` |
| **(Optional) Alibaba Cloud STS** | alibabacloud-sts20150401 | `>=1.2.0,<2.0.0` (extras `[alicloud]`) |

### Development / Test Dependencies

| Tool | Purpose |
|------|---------|
| `pytest` (`>=7.2.2`) | Unit test runner |
| `responses` (`>=0.5.1,<1.0.0`) | HTTP mocking for `requests` |
| `alibabacloud_sts20150401` | Required for `tests/test_alibaba_cloud.py` |

## Architecture Pattern

The project follows a **Command-Line Application Pattern** with:

- Modular authentication providers (Okta Classic, Okta Identity Engine)
- Pluggable MFA factor handlers (Okta factors, DUO, FIDO2, U2F)
- Strategy pattern for AWS / Alibaba Cloud role resolution (`DefaultResolver`)
- Dependency injection for UI abstraction (`UserInterface`)
- Shared utility layer (`common.py`) for HTTP session management, SAML parsing, OAuth token exchange, and cross-cutting concerns
- Mixin-based code reuse (`OktaHttpMixin`) for Okta HTTP client classes
- Dedicated debug/diagnostics layer (`debug_formatter.py`) with sensitive-data redaction and configuration source attribution
- Lazy-loaded, cached properties on `GimmeAWSCreds` (`config`, `okta`, `auth_session`, `aws_results`, `saml_data`, `aws_roles`)

## Installation Methods

1. **PyPI**: `pip install gimme-aws-creds`
2. **PyPI (with Alibaba Cloud)**: `pip install "gimme-aws-creds[alicloud]"`
3. **GitHub**: `pip install git+https://github.com/Nike-Inc/gimme-aws-creds`
4. **Homebrew (macOS)**: `brew install gimme-aws-creds`
5. **Nix**: `flake.nix` (`nix develop`) and `shell.nix` (`nix-shell`) provided
6. **Docker**: `Dockerfile` included; mount `~/.aws/credentials` and `~/.okta_aws_login_config` into the container

## Related Documentation

- [Architecture](./architecture.md)
- [README.md](../README.md) - End-user documentation
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guide
- [lambda/README.md](../lambda/README.md) - Optional gimme-creds-lambda proxy
