# gimme-aws-creds - Architecture Documentation

## Core Components

### 1. GimmeAWSCreds (main.py)

The main orchestrator class that:
- Initializes configuration and resolvers
- Detects Okta platform type (Classic vs Identity Engine) and instantiates the matching client
- Manages authentication session lifecycle
- Retrieves SAML assertions and exchanges them for AWS STS or Alibaba Cloud RAM credentials
- Handles credential output (file, stdout, JSON, `export`, `windows`)
- Supports both AWS STS and Alibaba Cloud RAM `AssumeRoleWithSAML`
- Discovers and applies environment-variable overrides through `envvar_list` / `envvar_conf_map`

**Key Properties (Lazy-loaded with caching):**
- `config` - Configuration object
- `okta_platform` - Detected platform type
- `okta` - Authentication client instance
- `auth_session` - Active authentication session
- `aws_results` - AWS app list from Okta
- `saml_data` - SAML assertion data
- `aws_roles` - Available AWS / Alibaba Cloud roles

### 2. Config (config.py)

Manages all configuration sources:
- Command-line arguments (`argparse`)
- Configuration file (`~/.okta_aws_login_config`, override via `OKTA_CONFIG`)
- Environment variables
- Profile inheritance via the `inherits = parent_profile` key
- Per-value source tracking (CLI / env / profile / inherited / default) consumed by `--debug` output

**Key Configuration Options:**
- `okta_org_url` - Okta organization URL
- `gimme_creds_server` - Credential server mode (`internal` / `appurl` / a gimme-creds-lambda URL)
- `client_id` - OAuth Client ID (required for OIE; also used by gimme-creds-lambda)
- `write_aws_creds` - Write to credentials file vs stdout
- `preferred_mfa_type` / `preferred_mfa_provider` / `duo_universal_factor` - Auto-select MFA factor
- `enable_alicloud` / `alicloud_saml_url` / `alicloud_region` - Alibaba Cloud (OIE-only)
- `output_format` - `export`, `json`, or `windows`
- `force_classic` / `open_browser` / `disable_keychain` / `remember_device`

### 3. Shared Utilities (common.py)

Central module for cross-cutting concerns, eliminating code duplication across the codebase:

- `user_agent()` - Canonical User-Agent string used by all HTTP callers
- `request_headers_json()` - Standard JSON `Accept` + `User-Agent` headers
- `parse_saml_form()` - Extracts `SAMLResponse`, `RelayState`, and form action from HTML
- `parse_saml_role_attributes()` - Yields role values from a base64 SAML assertion's XML attributes
- `create_http_session()` - Factory for `requests.Session` with retry logic, SSL configuration, and (when `debug=True`) a debug response hook from `debug_formatter`
- `OktaHttpMixin` - Shared OAuth-aware HTTP methods (`get`, `post`, `put`, `delete`, `check_kwargs`) inherited by both Okta client classes
- `okta_token_exchange()` - Shared Okta OAuth2 token exchange used by both OIE Web SSO and Alibaba Cloud Native-to-Web SSO interclient flows
- `FakeAssertion` - Stub assertion for when a real FIDO/WebAuthn device is unavailable
- `RoleSet` - Named tuple for role data (`idp`, `role`, `friendly_account_name`, `friendly_role_name`)

### 4. OktaClassicClient (okta_classic.py)

Handles authentication for Okta Classic domains. Inherits from `OktaHttpMixin`.

- Username/password authentication
- State token management
- MFA factor selection and verification (uses `_build_auth_flow_result()` helper for consistent token extraction)
- SAML response retrieval
- OAuth token exchange for gimme-creds-lambda

**Authentication Flow:**
1. POST credentials to `/api/v1/authn`
2. Handle MFA challenge (if required)
3. Exchange session token for SAML assertion
4. Optional: Device token registration

### 5. OktaIdentityEngine (okta_identity_engine.py)

Handles authentication for Okta Identity Engine domains. Inherits from `OktaHttpMixin`.

- OAuth 2.0 Device Authorization flow
- Web SSO token exchange (via shared `okta_token_exchange()`)
- Browser-based authentication (optionally auto-opened with `--open-browser`)
- Alibaba Cloud-aware scopes when `enable_alicloud` is set (adds `interclient_access`)

**Authentication Flow:**
1. POST to `/oauth2/v1/device/authorize`
2. User authenticates via browser
3. Poll `/oauth2/v1/token` for completion
4. Exchange tokens for Web SSO token (`urn:okta:oauth:token-type:web_sso_token`)
5. Retrieve SAML assertion

### 6. AwsResolver (aws.py)

Resolves AWS account and role information:

- Parses SAML assertions for IAM role ARNs (via shared `parse_saml_role_attributes()`)
- Fetches friendly account aliases by scraping the AWS sign-in page
- Supports both legacy and NextJS AWS console formats
- Recognizes standard AWS, AWS GovCloud, and AWS China partitions

### 7. AlibabaCloudClient (alibaba_cloud.py)

Handles Alibaba Cloud (AliCloud) RAM credential retrieval (OIE only):

- Native-to-Web SSO interclient OAuth token exchange with Okta (via shared `okta_token_exchange()`)
- SAML assertion retrieval for the Alibaba Cloud SAML app
- Alibaba Cloud RAM `AssumeRoleWithSAML` for temporary RAM credentials (region configurable, default `cn-hangzhou`)
- Output to `~/.aliyun/config.json` in the standard `aliyun` CLI format
- Optional - requires `alibabacloud-sts20150401` (install via `pip install "gimme-aws-creds[alicloud]"`)
- Sessions are capped at 3600 seconds by Alibaba Cloud STS; `aws_default_duration` is clamped accordingly

### 8. Debug Formatter (debug_formatter.py)

Provides structured, human-readable diagnostics activated by the `--debug` CLI flag:

- `setup_debug_logging()` - Wires a clean stderr formatter into the `gimme_aws_creds` logger
- `create_debug_response_hook()` - Hook attached to the shared `requests.Session` (via `create_http_session(debug=True)`) that logs both request and response with colorization
- `DebugFormatter` - Formats request/response with status-code coloring, sensitive header masking, and JSON pretty-printing
- `_redact_sensitive_debug_text()` - Regex-based scrubbing of SAML payloads, OAuth `actor_token` / `subject_token` values, `?token=` query params, and embedded `AssumeRoleWithSAMLResponse` XML
- `format_resolved_configuration()` - Emits a "Resolved Configuration" report showing the config file path, active profile, inheritance chain, CLI flags actually provided, environment variables consumed, effective `Config` attributes, and the merged profile dict, with the source of each value (`cli`, `env`, `profile`, `inherited from <parent>`, `default`)

Sensitive fields redacted by default include: `access_token`, `id_token`, `sessionToken`, `stateToken`, `password`, `SAMLResponse`, `SAMLAssertion`, `passCode`, `client_secret`, `actor_token`, `subject_token`, and the `Authorization` / `Cookie` / `Set-Cookie` headers.

### 9. UI Abstraction (ui.py)

Provides abstracted user interface:

- `UserInterface` - Base class
- `CLIUserInterface` - Command-line implementation
- Separates stdout (results) from stderr (messages)
- Environment and argument isolation for testing and programmatic use (`argv` / `environ` injection)

### 10. Default Resolver (default.py)

`DefaultResolver` provides interactive selection prompts for Okta apps and roles when none have been pre-configured for the active profile. Custom resolvers can implement `_enumerate_saml_roles` and `_display_role`.

### 11. Registered Authenticators (registered_authenticators.py)

Persists registered FIDO authenticator credential IDs (hashed with SHA-512) so a previously registered authenticator can be reused without re-enrollment.

## Authentication Flows

### Okta Classic Flow

```
User -> gimme-aws-creds -> Okta /api/v1/authn
                              |
                         MFA Challenge
                              |
                         Session Token
                              |
                    SAML Response from App Link
                              |
                         AWS STS
                              |
                    Temporary Credentials
```

### Okta Identity Engine Flow

```
User -> gimme-aws-creds -> /oauth2/v1/device/authorize
                              |
                    Device Code + Verification URL
                              |
                    User opens browser, authenticates
                              |
                    Poll /oauth2/v1/token
                              |
                    Access Token + ID Token
                              |
                    Web SSO Token Exchange (/oauth2/v1/token)
                              |
                    SAML Response
                              |
                    AWS STS  -or-  Alibaba Cloud RAM STS
                              |
                    Temporary Credentials
```

## MFA Factor Support

| Factor | Provider | Handler |
|--------|----------|---------|
| Push | Okta | `okta_classic.py` |
| TOTP | Okta / Google | `okta_classic.py` |
| SMS | Okta | `okta_classic.py` |
| Email | Okta | `okta_classic.py` |
| Call | Okta | `okta_classic.py` |
| U2F | Hardware | `u2f.py` |
| WebAuthn | Hardware / Software | `webauthn.py` (`dummy_webauthn.py` fallback on platforms where `ctap-keyring-device` is unavailable, e.g. Python 3.10+ on Windows) |
| DUO Push / Call / Passcode | DUO Security | `duo.py` |
| DUO Universal Prompt | DUO Security | `duo_universal.py` |

## Error Handling

Custom exception hierarchy in `errors.py`:

- `GimmeAWSCredsExitBase` - Base for exit-handling exceptions
- `GimmeAWSCredsExitSuccess` - Clean exit with optional result
- `GimmeAWSCredsExitError` - Error exit with message
- `GimmeAWSCredsError` - General operational error (used consistently for SAML errors, invalid ARNs, token exchange failures, and missing SDK dependencies)
- `GimmeAWSCredsMFAEnrollStatus` - MFA enrollment required

## Security Considerations

1. **Credential Storage**: Uses OS keyring for password storage (optional; can be disabled via `disable_keychain` / `--disable-keychain`)
2. **Device Tokens**: Okta device tokens stored in config for MFA bypass (also exposed via `OKTA_DEVICE_TOKEN` for CI use)
3. **FIDO Authenticators**: Credential IDs hashed with SHA-512 for storage in `registered_authenticators.py`
4. **SSL Verification**: Configurable but enabled by default (override with `--insecure` / `-k` - not recommended for production)
5. **Session Tokens**: Short-lived, not persisted to disk
6. **Debug Output Redaction**: `debug_formatter.py` redacts SAML payloads, OAuth tokens, passwords, authorization headers, cookies, and embedded `AssumeRoleWithSAMLResponse` XML before they reach stderr
7. **Credential Expiration**: `x_security_token_expires` (RFC3339) is written alongside credentials so external tools can refresh proactively

## Extension Points

1. **Custom Resolvers**: Implement `_enumerate_saml_roles` and `_display_role` (see `default.py`)
2. **UI Implementations**: Extend `UserInterface` for non-CLI use (`argv` / `environ` are dependency-injected)
3. **MFA Factors**: Add handlers in `_login_multi_factor` dispatch in `okta_classic.py`; use `_build_auth_flow_result()` for token extraction
4. **Shared HTTP Clients**: New Okta client classes can inherit `OktaHttpMixin` from `common.py` for consistent OAuth-aware HTTP methods
5. **SAML Parsing**: Use `parse_saml_form()` and `parse_saml_role_attributes()` from `common.py` for new SAML integrations
6. **Cloud Providers**: New provider modules can follow the `alibaba_cloud.py` pattern and reuse `okta_token_exchange()` for Okta-backed flows
7. **Debug Diagnostics**: Add new redaction rules in `debug_formatter._redact_sensitive_debug_text()` or extend `_CONFIG_OBJECT_ATTRS` to surface new config attributes in the resolved-configuration report
