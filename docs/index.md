# gimme-aws-creds - Project Documentation Index

> **AI-Assisted Development Reference** - This documentation provides comprehensive context for AI agents working with the gimme-aws-creds codebase.

## Project Overview

**Type:** CLI (Python command-line tool)
**Language:** Python 3.10+
**Architecture:** Modular authentication system with pluggable MFA providers
**Released Version:** 2.8.2
**Latest Version:** 2.9.0-pre

### Quick Reference

| Property | Value |
|----------|-------|
| **Tech Stack** | Python 3.10+, boto3, requests, fido2 |
| **Entry Point** | `bin/gimme-aws-creds` -> `gimme_aws_creds.main` |
| **Config File** | `~/.okta_aws_login_config` (override via `OKTA_CONFIG`) |
| **AWS Output** | `~/.aws/credentials` or stdout |
| **Alibaba Cloud Output** | `~/.aliyun/config.json` or stdout (override via `ALIBABA_CLOUD_SHARED_CREDENTIALS_FILE`) |

## Generated Documentation

### Core Documentation

- [Project Overview](./project-overview.md) - Executive summary, features, tech stack
- [Architecture](./architecture.md) - System design, components, authentication flows

## Existing Documentation

The following documentation exists in the repository root:

- [README.md](../README.md) - Comprehensive user documentation
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [LICENSE](../LICENSE) - Apache License 2.0
- [lambda/README.md](../lambda/README.md) - Lambda deployment guide

## Getting Started

### For Development

```bash
# Clone and setup
git clone https://github.com/Nike-Inc/gimme-aws-creds.git
cd gimme-aws-creds
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements_dev.txt
pip install -e .

# Run tests
pytest -vv tests
```

### For Usage

```bash
# Configure
gimme-aws-creds --action-configure

# Get credentials
gimme-aws-creds

# Debug a configuration / authentication issue
gimme-aws-creds --debug
```

## Module Quick Reference

| Module | Purpose |
|--------|---------|
| `main.py` | Main orchestrator, credential handling, AWS/AliCloud dispatch |
| `common.py` | Shared utilities: HTTP session factory, SAML parsing, `user_agent()`, `request_headers_json()`, `OktaHttpMixin`, `okta_token_exchange()`, `FakeAssertion`, `RoleSet` |
| `config.py` | Configuration management (CLI args, profiles, env vars, source tracking for `--debug`) |
| `debug_formatter.py` | HTTP request/response debug formatting, sensitive-data redaction, resolved-configuration reporting |
| `okta_classic.py` | Okta Classic authentication + MFA |
| `okta_identity_engine.py` | Okta Identity Engine (OIE) auth via Device Authorization flow |
| `aws.py` | AWS role resolution, SAML parsing, account-alias lookup |
| `alibaba_cloud.py` | Alibaba Cloud (AliCloud) RAM credential support (Native-to-Web SSO) |
| `duo.py` / `duo_universal.py` | DUO MFA handlers (iframe + Universal Prompt) |
| `webauthn.py` / `dummy_webauthn.py` / `u2f.py` | FIDO2 / hardware key MFA (`dummy_webauthn.py` is a fallback used when WebAuthn is unavailable on the platform) |
| `registered_authenticators.py` | Persists registered FIDO authenticator credential IDs |
| `default.py` | Default `Resolver` implementation for app/role enumeration prompts |
| `ui.py` | User interface abstraction (`UserInterface`, `CLIUserInterface`) |
| `errors.py` | Exception hierarchy |

## Authentication Flows

### Okta Classic
1. Username/password -> Okta authn API
2. MFA challenge (if required)
3. Session token -> SAML assertion
4. AWS STS -> Temporary credentials

### Okta Identity Engine
1. Device authorization request
2. User authenticates in browser
3. Token exchange -> Web SSO token
4. SAML assertion -> AWS STS (or Alibaba Cloud STS for AliCloud profiles)

## Cloud Provider Support

| Provider | Auth Flow | STS API | Output |
|----------|-----------|---------|--------|
| **AWS** | Classic or OIE | `sts:AssumeRoleWithSAML` (boto3) | `~/.aws/credentials` |
| **Alibaba Cloud** | OIE only (Native-to-Web SSO) | RAM `AssumeRoleWithSAML` (alibabacloud-sts SDK) | `~/.aliyun/config.json` |

Alibaba Cloud support is opt-in via the `gimme-aws-creds[alicloud]` extra and the `enable_alicloud` profile setting.

## Key Integration Points

- **Okta APIs**: `/api/v1/authn`, `/oauth2/v1/device/authorize`, `/oauth2/v1/token`
- **AWS STS**: `assume_role_with_saml` (standard, GovCloud, and China partitions)
- **Alibaba Cloud STS**: `AssumeRoleWithSAML` (1 hour session cap)
- **DUO Security**: iframe + Universal Prompt flows
- **FIDO2 / WebAuthn**: Hardware authenticator support via `fido2` and `ctap-keyring-device`

## Debug & Troubleshooting

The `--debug` flag enables structured HTTP request/response logging via `debug_formatter.py`:

- Colorized request/response sections written to stderr
- Sensitive fields (`access_token`, `id_token`, `sessionToken`, `stateToken`, `password`, `SAMLResponse`, `SAMLAssertion`, `passCode`, `Authorization`, `Cookie`, etc.) are redacted
- Embedded `AssumeRoleWithSAMLResponse` payloads from AWS STS are redacted
- A "Resolved Configuration" report shows the final config values and the source of each (CLI flag, env var, profile, inheritance, default)

---

*Documentation generated: 2026-01-09*
*Last updated: 2026-05-05*
*Scan level: exhaustive*
