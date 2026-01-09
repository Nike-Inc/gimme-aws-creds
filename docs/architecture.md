# gimme-aws-creds - Architecture Documentation

## System Overview

gimme-aws-creds is a CLI tool that bridges Okta SAML authentication with AWS STS credential retrieval. The architecture is designed for extensibility across multiple Okta platforms and MFA providers.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                         │
│                      bin/gimme-aws-creds                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GimmeAWSCreds                            │
│                         (main.py)                               │
│  • Orchestrates authentication flow                             │
│  • Manages configuration                                        │
│  • Handles credential output                                    │
└─────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   Config          │ │   Okta Auth       │ │   AWS Resolver    │
│   (config.py)     │ │   Providers       │ │   (aws.py)        │
│                   │ │                   │ │                   │
│ • CLI args        │ │ • OktaClassic     │ │ • SAML parsing    │
│ • Config file     │ │ • OktaIdentityEng │ │ • Role resolution │
│ • Env vars        │ │                   │ │ • Alias lookup    │
└───────────────────┘ └───────────────────┘ └───────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   MFA Handlers    │ │   FIDO/WebAuthn   │ │   DUO Handlers    │
│                   │ │                   │ │                   │
│ • Push            │ │ • webauthn.py     │ │ • duo.py          │
│ • TOTP            │ │ • u2f.py          │ │ • duo_universal.py│
│ • SMS/Email/Call  │ │                   │ │                   │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

## Core Components

### 1. GimmeAWSCreds (main.py)

The main orchestrator class that:
- Initializes configuration and resolvers
- Detects Okta platform type (Classic vs Identity Engine)
- Manages authentication session lifecycle
- Retrieves SAML assertions and exchanges for AWS credentials
- Handles credential output (file, stdout, JSON)

**Key Properties (Lazy-loaded with caching):**
- `config` - Configuration object
- `okta_platform` - Detected platform type
- `okta` - Authentication client instance
- `auth_session` - Active authentication session
- `aws_results` - AWS app list from Okta
- `saml_data` - SAML assertion data
- `aws_roles` - Available AWS roles

### 2. Config (config.py)

Manages all configuration sources:
- Command-line arguments (argparse)
- Configuration file (`~/.okta_aws_login_config`)
- Environment variables
- Profile inheritance support

**Key Configuration Options:**
- `okta_org_url` - Okta organization URL
- `gimme_creds_server` - Credential server mode (internal/appurl/lambda URL)
- `client_id` - OAuth Client ID (required for OIE)
- `write_aws_creds` - Write to credentials file vs stdout
- `preferred_mfa_type` - Auto-select MFA factor

### 3. OktaClassicClient (okta_classic.py)

Handles authentication for Okta Classic domains:
- Username/password authentication
- State token management
- MFA factor selection and verification
- SAML response retrieval
- OAuth token exchange for gimme-creds-lambda

**Authentication Flow:**
1. POST credentials to `/api/v1/authn`
2. Handle MFA challenge (if required)
3. Exchange session token for SAML assertion
4. Optional: Device token registration

### 4. OktaIdentityEngine (okta_identity_engine.py)

Handles authentication for Okta Identity Engine domains:
- OAuth 2.0 Device Authorization flow
- Web SSO token exchange
- Browser-based authentication

**Authentication Flow:**
1. POST to `/oauth2/v1/device/authorize`
2. User authenticates via browser
3. Poll for token completion
4. Exchange tokens for Web SSO token
5. Retrieve SAML assertion

### 5. AwsResolver (aws.py)

Resolves AWS account and role information:
- Parses SAML assertions for role ARNs
- Fetches friendly names from AWS sign-in page
- Supports both legacy and NextJS AWS console formats

### 6. UI Abstraction (ui.py)

Provides abstracted user interface:
- `UserInterface` - Base class
- `CLIUserInterface` - Command-line implementation
- Separates stdout (results) from stderr (messages)
- Environment and argument isolation for testing

## Authentication Flows

### Okta Classic Flow

```
User → gimme-aws-creds → Okta /api/v1/authn
                              ↓
                         MFA Challenge
                              ↓
                         Session Token
                              ↓
                    SAML Response from App Link
                              ↓
                         AWS STS
                              ↓
                    Temporary Credentials
```

### Okta Identity Engine Flow

```
User → gimme-aws-creds → /oauth2/v1/device/authorize
                              ↓
                    Device Code + Verification URL
                              ↓
                    User opens browser, authenticates
                              ↓
                    Poll /oauth2/v1/token
                              ↓
                    Access Token + ID Token
                              ↓
                    Web SSO Token Exchange
                              ↓
                    SAML Response
                              ↓
                    AWS STS → Temporary Credentials
```

## MFA Factor Support

| Factor | Provider | Handler |
|--------|----------|---------|
| Push | Okta | okta_classic.py |
| TOTP | Okta/Google | okta_classic.py |
| SMS | Okta | okta_classic.py |
| Email | Okta | okta_classic.py |
| Call | Okta | okta_classic.py |
| U2F | Hardware | u2f.py |
| WebAuthn | Hardware/Software | webauthn.py |
| DUO Push/Call/Passcode | DUO Security | duo.py |
| DUO Universal Prompt | DUO Security | duo_universal.py |

## Error Handling

Custom exception hierarchy in `errors.py`:
- `GimmeAWSCredsExitBase` - Base for exit-handling exceptions
- `GimmeAWSCredsExitSuccess` - Clean exit with optional result
- `GimmeAWSCredsExitError` - Error exit with message
- `GimmeAWSCredsError` - General operational error
- `GimmeAWSCredsMFAEnrollStatus` - MFA enrollment required

## Security Considerations

1. **Credential Storage**: Uses OS keyring for password storage (optional)
2. **Device Tokens**: Okta device tokens stored in config for MFA bypass
3. **FIDO Authenticators**: Credential IDs hashed with SHA-512 for storage
4. **SSL Verification**: Configurable but enabled by default
5. **Session Tokens**: Short-lived, not persisted

## Extension Points

1. **Custom Resolvers**: Implement `_enumerate_saml_roles` and `_display_role`
2. **UI Implementations**: Extend `UserInterface` for non-CLI use
3. **MFA Factors**: Add handlers in `_login_multi_factor` dispatch
