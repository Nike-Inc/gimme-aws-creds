# gimme-aws-creds - Project Documentation Index

> **AI-Assisted Development Reference** - This documentation provides comprehensive context for AI agents working with the gimme-aws-creds codebase.

## Project Overview

**Type:** CLI (Python command-line tool)  
**Language:** Python 3.7+  
**Architecture:** Modular authentication system with pluggable MFA providers  
**Released Version:** 2.8.2
**Latest Version:** 2.9.0-pre

### Quick Reference

| Property | Value |
|----------|-------|
| **Tech Stack** | Python 3.7+, boto3, requests, fido2 |
| **Entry Point** | `bin/gimme-aws-creds` → `gimme_aws_creds.main` |
| **Config File** | `~/.okta_aws_login_config` |
| **Output** | `~/.aws/credentials` or stdout |

## Generated Documentation

### Core Documentation

- [Project Overview](./project-overview.md) - Executive summary, features, tech stack
- [Architecture](./architecture.md) - System design, components, authentication flows
- [Source Tree Analysis](./source-tree-analysis.md) - Directory structure, module responsibilities
- [Development Guide](./development-guide.md) - Setup, testing, contributing

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
```

## Module Quick Reference

| Module | Purpose |
|--------|---------|
| `main.py` | Main orchestrator, credential handling |
| `config.py` | Configuration management |
| `okta_classic.py` | Okta Classic authentication + MFA |
| `okta_identity_engine.py` | Okta Identity Engine (OIE) auth |
| `aws.py` | AWS role resolution, SAML parsing |
| `duo.py` / `duo_universal.py` | DUO MFA handlers |
| `webauthn.py` / `u2f.py` | FIDO/hardware key MFA |
| `ui.py` | User interface abstraction |
| `errors.py` | Exception hierarchy |

## Authentication Flows

### Okta Classic
1. Username/password → Okta authn API
2. MFA challenge (if required)
3. Session token → SAML assertion
4. AWS STS → Temporary credentials

### Okta Identity Engine
1. Device authorization request
2. User authenticates in browser
3. Token exchange → Web SSO token
4. SAML assertion → AWS STS

## Key Integration Points

- **Okta APIs**: `/api/v1/authn`, `/oauth2/v1/*`
- **AWS STS**: `assume_role_with_saml`
- **DUO Security**: iframe/Universal Prompt flows
- **FIDO2**: Hardware authenticator support

---

*Documentation generated: 2026-01-09*  
*Scan level: exhaustive*
