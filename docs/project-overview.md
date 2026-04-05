# gimme-aws-creds - Project Overview

## Executive Summary

**gimme-aws-creds** is a Python CLI tool that acquires temporary AWS credentials via AWS STS using Okta as a SAML Identity Provider (IdP). It supports both Okta Classic and Okta Identity Engine authentication flows with comprehensive MFA support.

## Project Metadata

| Property | Value |
|----------|-------|
| **Name** | gimme-aws-creds |
| **Released Version** | 2.8.2 |
| **Latest Version** | 2.9.0-pre |
| **License** | Apache License 2.0 |
| **Python** | 3.7+ |
| **Maintainer** | Eric Pierce |
| **Repository** | https://github.com/Nike-Inc/gimme-aws-creds |

## Purpose & Problem Solved

Organizations using Okta for SSO to AWS need a way to obtain temporary AWS credentials for CLI/API access. gimme-aws-creds solves this by:

1. Authenticating users via Okta (Classic or Identity Engine)
2. Handling multi-factor authentication (MFA) flows
3. Retrieving SAML assertions from Okta
4. Exchanging SAML assertions for AWS STS temporary credentials
5. Writing credentials to `~/.aws/credentials` or outputting to stdout

## Key Features

- **Dual Okta Platform Support**: Works with both Okta Classic and Okta Identity Engine domains
- **Comprehensive MFA**: Push, TOTP, SMS, Email, Voice Call, DUO, WebAuthn, U2F, Hardware Tokens
- **Multiple Output Formats**: Shell exports, JSON, Windows PowerShell
- **Profile Management**: Multiple configuration profiles with inheritance
- **AWS Account Resolution**: Resolves account IDs to friendly aliases
- **Credential Storage**: Automatic storage in AWS credentials file with expiration tracking
- **Lambda Integration**: Optional gimme-creds-lambda proxy for API key-less operation

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| **Language** | Python | `3.7+` |
| **AWS SDK** | boto3 | `>=1.7.70,<2.0.0` |
| **HTTP** | requests | `>=2.25.0,<3.0.0` |
| **HTML Parsing** | beautifulsoup4 | `>=4.6.0,<5.0.0` |
| **Okta SDK** | okta | `>=2.9.0,<3.0.0` |
| **FIDO2/WebAuthn** | fido2 | `>=0.9.1,<0.10.0` |
| **JWT** | pyjwt | `>=2.4.0,<3.0.0` |
| **Keyring** | keyring | `>=21.4.0` |
| **HTML5** | html5lib | `>=1.1,<2.0.0` |
| **URL Parsing** | furl | `>=2.1.4,<3.0.0` |

## Architecture Pattern

The project follows a **Command-Line Application Pattern** with:
- Modular authentication providers (Okta Classic, Okta Identity Engine)
- Pluggable MFA factor handlers
- Strategy pattern for AWS role resolution
- Dependency injection for UI abstraction

## Installation Methods

1. **PyPI**: `pip install gimme-aws-creds`
2. **GitHub**: `pip install git+github.com/Nike-Inc/gimme-aws-creds`
3. **Homebrew**: `brew install gimme-aws-creds`
4. **Nix**: Flake and shell.nix support
5. **Docker**: Dockerfile included

## Related Documentation

- [Architecture](./architecture.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Development Guide](./development-guide.md)
