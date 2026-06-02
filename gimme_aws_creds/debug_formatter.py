"""
Debug formatting utilities for gimme-aws-creds.
Provides clean, readable output for HTTP request/response debugging.
"""
import json
import logging
import re
import sys

logger = logging.getLogger(__name__)


class DebugFormatter:
    """Formats HTTP request/response data for readable debug output"""
    
    # ANSI color codes (disabled if not a TTY)
    COLORS_ENABLED = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    
    # Color definitions
    CYAN = '\033[96m' if COLORS_ENABLED else ''
    GREEN = '\033[92m' if COLORS_ENABLED else ''
    YELLOW = '\033[93m' if COLORS_ENABLED else ''
    RED = '\033[91m' if COLORS_ENABLED else ''
    BLUE = '\033[94m' if COLORS_ENABLED else ''
    MAGENTA = '\033[95m' if COLORS_ENABLED else ''
    BOLD = '\033[1m' if COLORS_ENABLED else ''
    DIM = '\033[2m' if COLORS_ENABLED else ''
    RESET = '\033[0m' if COLORS_ENABLED else ''
    
    # Sensitive fields that should be REDACTED
    SENSITIVE_FIELDS = [
        'access_token', 'id_token', 'sessionToken', 'stateToken',
        'password', 'SAMLResponse', 'SAMLAssertion', 'passCode',
        'client_secret', 'actor_token', 'subject_token',
        'Authorization', 'Cookie', 'Set-Cookie'
    ]
    
    @classmethod
    def format_request(cls, request):
        """Format HTTP request for debug output"""
        lines = []
        
        # Request line with method and URL
        lines.append("")
        lines.append(f"{cls.CYAN}{cls.BOLD}{'─' * 70}{cls.RESET}")
        lines.append(f"{cls.GREEN}{cls.BOLD}▶ REQUEST{cls.RESET}")
        lines.append(f"{cls.CYAN}{cls.BOLD}{'─' * 70}{cls.RESET}")
        request_url = _redact_sensitive_debug_text(request.url)
        lines.append(f"  {cls.BOLD}{request.method}{cls.RESET} {cls.BLUE}{request_url}{cls.RESET}")
        
        # Headers
        lines.append(f"\n  {cls.YELLOW}Headers:{cls.RESET}")
        headers = cls._mask_sensitive_headers(dict(request.headers))
        for key, value in headers.items():
            lines.append(f"    {cls.DIM}{key}:{cls.RESET} {value}")
        
        # Body
        if request.body:
            lines.append(f"\n  {cls.YELLOW}Body:{cls.RESET}")
            body_str = cls._format_body(request.body)
            for line in body_str.split('\n'):
                lines.append(f"    {line}")
        
        return '\n'.join(lines)
    
    @classmethod
    def format_response(cls, response):
        """Format HTTP response for debug output"""
        lines = []
        
        # Status line with color based on status code
        status_color = cls._get_status_color(response.status_code)
        
        lines.append(f"\n  {cls.MAGENTA}{cls.BOLD}◀ RESPONSE{cls.RESET}")
        lines.append(f"  {status_color}{cls.BOLD}{response.status_code}{cls.RESET} {response.reason}")
        
        # Headers
        lines.append(f"\n  {cls.YELLOW}Headers:{cls.RESET}")
        headers = cls._mask_sensitive_headers(dict(response.headers))
        for key, value in headers.items():
            # Truncate long header values
            if len(str(value)) > 100:
                value = str(value)[:100] + "..."
            lines.append(f"    {cls.DIM}{key}:{cls.RESET} {value}")
        
        # Body
        lines.append(f"\n  {cls.YELLOW}Body:{cls.RESET}")
        try:
            response_json = response.json()
            REDACTED_json = cls._mask_sensitive_dict(response_json)
            body_str = json.dumps(REDACTED_json, indent=2)
            for line in body_str.split('\n'):
                lines.append(f"    {line}")
        except (json.JSONDecodeError, ValueError):
            body = _redact_sensitive_debug_text(response.text)
            body = body[:500] + "..." if len(body) > 500 else body
            for line in body.split('\n')[:20]:  # Limit to first 20 lines
                lines.append(f"    {line}")
        
        lines.append(f"{cls.CYAN}{cls.BOLD}{'─' * 70}{cls.RESET}")
        lines.append("")
        
        return '\n'.join(lines)
    
    @classmethod
    def _get_status_color(cls, status_code):
        """Return appropriate color for HTTP status code"""
        if 200 <= status_code < 300:
            return cls.GREEN
        elif 300 <= status_code < 400:
            return cls.YELLOW
        elif 400 <= status_code < 500:
            return cls.RED
        elif status_code >= 500:
            return cls.RED + cls.BOLD
        return cls.RESET
    
    @classmethod
    def _format_body(cls, body):
        """Format request body for display"""
        try:
            # Handle bytes
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            
            # Try to parse as JSON
            parsed = json.loads(body)
            REDACTED = cls._mask_sensitive_dict(parsed)
            return json.dumps(REDACTED, indent=2)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            # Return as-is if not JSON, truncated if too long
            body_str = _redact_sensitive_debug_text(str(body))
            if len(body_str) > 500:
                return body_str[:500] + "..."
            return body_str
    
    @classmethod
    def _mask_sensitive_dict(cls, data):
        """Recursively mask sensitive fields in a dictionary"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key.lower() in [f.lower() for f in cls.SENSITIVE_FIELDS]:
                    result[key] = "[REDACTED]" if value else value
                elif isinstance(value, dict):
                    result[key] = cls._mask_sensitive_dict(value)
                elif isinstance(value, list):
                    result[key] = [cls._mask_sensitive_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    result[key] = value
            return result
        return data
    
    @classmethod
    def _mask_sensitive_headers(cls, headers):
        """Mask sensitive header values"""
        result = {}
        sensitive_header_names = ['authorization', 'cookie', 'set-cookie', 'x-okta-session-id']
        
        for key, value in headers.items():
            if key.lower() in sensitive_header_names:
                if value and len(str(value)) > 20:
                    result[key] = str(value)[:20] + "...[REDACTED]"
                elif value:
                    result[key] = "[REDACTED]"
                else:
                    result[key] = value
            else:
                result[key] = value
        return result


_SAML_VALUE_FIELD_RE = re.compile(
    r"(\b(?:SAMLAssertion|SAMLResponse)\b['\"]?\s*[:=]\s*b?)(['\"])(.*?)(\2)",
    re.IGNORECASE | re.DOTALL,
)
_SAML_FORM_FIELD_RE = re.compile(
    r"(\b(?:SAMLAssertion|SAMLResponse)=)([^&\s'\"\\]+)",
    re.IGNORECASE,
)
_OAUTH_EXCHANGE_TOKEN_VALUE_FIELD_RE = re.compile(
    r"(\b(?:actor_token|subject_token)\b['\"]?\s*[:=]\s*b?)(['\"])(.*?)(\2)",
    re.IGNORECASE | re.DOTALL,
)
_OAUTH_EXCHANGE_TOKEN_FORM_FIELD_RE = re.compile(
    r"(\b(?:actor_token|subject_token)=)([^&\s'\"\\]+)",
    re.IGNORECASE,
)
_URL_TOKEN_QUERY_PARAM_RE = re.compile(
    r"([?&]token=)([^&\s'\"\\]+)",
    re.IGNORECASE,
)
_SAML_HTML_INPUT_RE = re.compile(
    r"(\bname=(['\"])SAMLResponse\2[^>]*\bvalue=)(['\"])(.*?)(\3)",
    re.IGNORECASE | re.DOTALL,
)
_ASSUME_ROLE_WITH_SAML_RESPONSE_BODY_RE = re.compile(
    r"(Response body:\s*).*AssumeRoleWithSAMLResponse.*",
    re.IGNORECASE | re.DOTALL,
)
_ASSUME_ROLE_WITH_SAML_RESPONSE_XML_RE = re.compile(
    r"<AssumeRoleWithSAMLResponse\b.*?</AssumeRoleWithSAMLResponse>",
    re.IGNORECASE | re.DOTALL,
)


def _redact_sensitive_debug_text(text):
    """Redact SAML payloads from debug text while leaving operation names visible."""
    if not isinstance(text, str):
        text = str(text)

    text = _ASSUME_ROLE_WITH_SAML_RESPONSE_BODY_RE.sub(
        r"\1[AWS STS SAML response redacted]",
        text,
    )
    text = _ASSUME_ROLE_WITH_SAML_RESPONSE_XML_RE.sub(
        "[AWS STS SAML response redacted]",
        text,
    )
    text = _SAML_HTML_INPUT_RE.sub(r"\1\3[REDACTED]\3", text)
    text = _SAML_VALUE_FIELD_RE.sub(r"\1\2[REDACTED]\4", text)
    text = _SAML_FORM_FIELD_RE.sub(r"\1[REDACTED]", text)
    text = _OAUTH_EXCHANGE_TOKEN_VALUE_FIELD_RE.sub(r"\1\2[REDACTED]\4", text)
    text = _OAUTH_EXCHANGE_TOKEN_FORM_FIELD_RE.sub(r"\1[REDACTED]", text)
    text = _URL_TOKEN_QUERY_PARAM_RE.sub(r"\1[REDACTED]", text)
    return text


# Substrings that indicate a config key should be REDACTED in --debug output.
_SENSITIVE_CONFIG_SUBSTRINGS = ('password', 'device_token', 'api_key')

# Config attributes (on Config object) that we display alongside the
# profile-merged conf_dict. Only attributes meaningful to the user.
# (aws_default_duration is intentionally omitted: it's derived from conf_dict
# and reported there with the correct profile/env/cli source.)
_CONFIG_OBJECT_ATTRS = (
    'OKTA_CONFIG',
    'conf_profile',
    'username',
    'api_key',
    'verify_ssl_certs',
    'app_url',
    'resolve',
    'mfa_code',
    'remember_device',
    'device_token',
    'output_format',
    'force_classic',
    'open_browser',
    'disable_keychain',
    'enable_alicloud',
    'roles',
    'cred_profile',
    'debug',
    'action_configure',
    'action_list_profiles',
    'action_list_roles',
    'action_store_json_creds',
    'action_register_device',
    'action_setup_fido_authenticator',
    'action_output_format',
)


def _mask_config_value(key, value):
    """Mask values for keys that look sensitive (passwords, tokens, etc.)."""
    if value is None or value == '' or value is False:
        return value
    key_lower = str(key).lower()
    if any(s in key_lower for s in _SENSITIVE_CONFIG_SUBSTRINGS):
        s = str(value)
        if len(s) > 8:
            return s[:4] + '...[REDACTED]'
        return '[REDACTED]'
    return value


def format_resolved_configuration(config, conf_dict, env_overrides_applied=None,
                                  cli_overrides_applied=None):
    """Format the resolved configuration for --debug output.

    Shows:
      - Configuration file path (and whether OKTA_CONFIG env var set it)
      - Active profile and inheritance chain
      - CLI arguments explicitly provided
      - Environment variables affecting configuration
      - Effective Config object attributes
      - Effective profile-merged conf_dict, with the source of each value

    :param config: gimme_aws_creds.config.Config instance (after get_args() and
        get_config_dict() have run)
    :param conf_dict: the merged profile config dict
    :param env_overrides_applied: dict of {conf_key: env_var_name} for env vars
        that overrode profile values in conf_dict
    :param cli_overrides_applied: dict of {conf_key: cli_flag_name} for CLI
        flags that overrode profile values in conf_dict
    """
    env_overrides_applied = env_overrides_applied or {}
    cli_overrides_applied = cli_overrides_applied or {}

    df = DebugFormatter
    bar = f"{df.CYAN}{df.BOLD}{'═' * 70}{df.RESET}"
    sub_bar = f"{df.CYAN}{'─' * 70}{df.RESET}"

    lines = ['']
    lines.append(bar)
    lines.append(f"{df.CYAN}{df.BOLD}  RESOLVED CONFIGURATION{df.RESET}")
    lines.append(bar)
    lines.append('')

    # --- Configuration file ---
    okta_config_path = getattr(config, 'OKTA_CONFIG', None)
    env_used_in_init = getattr(config, '_env_used_in_init', {}) or {}
    if 'OKTA_CONFIG' in env_used_in_init:
        path_source = 'env: OKTA_CONFIG'
    else:
        path_source = 'default location (~/.okta_aws_login_config)'
    lines.append(
        f"  {df.YELLOW}Configuration file:{df.RESET} {okta_config_path} "
        f"{df.DIM}[{path_source}]{df.RESET}"
    )

    # --- Active profile / inheritance chain ---
    conf_profile = getattr(config, 'conf_profile', None)
    if 'profile' in (getattr(config, '_cli_args_provided', {}) or {}):
        profile_source = 'cli: --profile'
    elif conf_profile == 'DEFAULT':
        profile_source = 'default'
    else:
        profile_source = 'set programmatically'
    lines.append(
        f"  {df.YELLOW}Active profile:{df.RESET}     {conf_profile} "
        f"{df.DIM}[{profile_source}]{df.RESET}"
    )

    chain = getattr(config, '_inheritance_chain', []) or []
    if len(chain) > 1:
        lines.append(
            f"  {df.YELLOW}Inheritance chain:{df.RESET}  "
            + ' -> '.join(chain)
            + f" {df.DIM}(child overrides parent){df.RESET}"
        )
    lines.append('')

    # --- CLI arguments provided ---
    cli_args_provided = getattr(config, '_cli_args_provided', {}) or {}
    if cli_args_provided:
        lines.append(f"  {df.YELLOW}CLI arguments provided:{df.RESET}")
        for dest in sorted(cli_args_provided.keys()):
            value = cli_args_provided[dest]
            display = _mask_config_value(dest, value)
            flag = '--' + dest.replace('_', '-')
            lines.append(f"    {flag} = {display}")
        lines.append('')

    # --- Environment variables affecting configuration ---
    env_used = dict(env_used_in_init)
    for conf_key, env_var in env_overrides_applied.items():
        env_used[env_var] = {
            'sets': f'conf_dict.{conf_key}',
            'value': config.ui.environ.get(env_var) if hasattr(config, 'ui') else None,
        }
    if env_used:
        lines.append(f"  {df.YELLOW}Environment variables affecting configuration:{df.RESET}")
        for env_name in sorted(env_used.keys()):
            info = env_used[env_name]
            display = _mask_config_value(env_name, info.get('value'))
            lines.append(
                f"    {env_name} = {display} "
                f"{df.DIM}-> {info.get('sets', '')}{df.RESET}"
            )
        lines.append('')

    # --- Config object attributes ---
    lines.append(f"  {df.YELLOW}Config object (CLI/env/runtime values):{df.RESET}")
    lines.append(sub_bar)
    for attr in _CONFIG_OBJECT_ATTRS:
        if not hasattr(config, attr):
            continue
        value = getattr(config, attr)
        display = _mask_config_value(attr, value)
        source = _config_attr_source(config, attr, env_used_in_init)
        lines.append(_format_kv_line(attr, display, source))
    lines.append('')

    # --- Effective profile-merged conf_dict ---
    profile_sources = getattr(config, '_profile_value_sources', {}) or {}
    lines.append(f"  {df.YELLOW}Effective profile config (merged conf_dict):{df.RESET}")
    lines.append(sub_bar)
    if conf_dict:
        for key in sorted(conf_dict.keys()):
            value = conf_dict[key]
            display = _mask_config_value(key, value)
            if key in cli_overrides_applied:
                source = f"cli: {cli_overrides_applied[key]}"
            elif key in env_overrides_applied:
                source = f"env: {env_overrides_applied[key]}"
            elif key in profile_sources:
                source = f"profile: {profile_sources[key]}"
            else:
                source = "computed/default"
            lines.append(_format_kv_line(key, display, source))
    else:
        lines.append(f"    {df.DIM}(empty){df.RESET}")
    lines.append('')
    lines.append(bar)
    lines.append('')

    return '\n'.join(lines)


def _config_attr_source(config, attr, env_used_in_init):
    """Best-effort determination of where a Config attribute came from."""
    cli_args = getattr(config, '_cli_args_provided', {}) or {}

    cli_attr_to_flag = {
        'username': '--username',
        'mfa_code': '--mfa-code',
        'remember_device': '--remember-device',
        'output_format': '--output-format',
        'action_output_format': '--output-format',
        'roles': '--roles',
        'cred_profile': '--aws-cred-profile',
        'conf_profile': '--profile',
        'debug': '--debug',
        'enable_alicloud': '--enable-alicloud',
        'force_classic': '--force-classic',
        'open_browser': '--open-browser',
        'disable_keychain': '--disable-keychain',
        'resolve': '--resolve',
        'action_configure': '--action-configure',
        'action_list_profiles': '--action-list-profiles',
        'action_list_roles': '--action-list-roles',
        'action_store_json_creds': '--action-store-json-creds',
        'action_register_device': '--action-register-device',
        'action_setup_fido_authenticator': '--action-setup-fido-authenticator',
    }
    cli_attr_to_dest = {
        'username': 'username',
        'mfa_code': 'mfa_code',
        'remember_device': 'remember_device',
        'output_format': 'output_format',
        'action_output_format': 'output_format',
        'roles': 'roles',
        'cred_profile': 'aws_cred_profile',
        'conf_profile': 'profile',
        'debug': 'debug',
        'enable_alicloud': 'enable_alicloud',
        'force_classic': 'force_classic',
        'open_browser': 'open_browser',
        'disable_keychain': 'disable_keychain',
        'resolve': 'resolve',
        'action_configure': 'action_configure',
        'action_list_profiles': 'action_list_profiles',
        'action_list_roles': 'action_list_roles',
        'action_store_json_creds': 'action_store_json_creds',
        'action_register_device': 'action_register_device',
        'action_setup_fido_authenticator': 'action_setup_fido_authenticator',
    }

    if attr == 'verify_ssl_certs':
        if 'insecure' in cli_args:
            return 'cli: --insecure'
        return 'default'
    if attr == 'OKTA_CONFIG':
        if 'OKTA_CONFIG' in env_used_in_init:
            return 'env: OKTA_CONFIG'
        return 'default'
    if attr == 'username':
        if 'username' in cli_args:
            return 'cli: --username'
        if 'OKTA_USERNAME' in env_used_in_init:
            return 'env: OKTA_USERNAME'
        return 'default/unset'
    if attr == 'api_key':
        if 'OKTA_API_KEY' in env_used_in_init:
            return 'env: OKTA_API_KEY'
        return 'default/unset'

    if attr in cli_attr_to_dest and cli_attr_to_dest[attr] in cli_args:
        return f"cli: {cli_attr_to_flag[attr]}"
    return 'default'


def _format_kv_line(key, value, source):
    """Render a single 'key = value [source]' line with consistent alignment."""
    df = DebugFormatter
    key_str = f"{str(key):<32}"
    value_str = str(value) if value is not None else 'None'
    if len(value_str) > 60:
        value_str = value_str[:60] + '...'
    return f"    {df.BOLD}{key_str}{df.RESET} = {value_str:<40} {df.DIM}[{source}]{df.RESET}"


def create_debug_response_hook(mask_func=None):
    """Create a response hook for requests library that logs debug info"""
    
    def debug_response_hook(response, *args, **kwargs):
        """Log request and response details for debugging"""
        request = response.request
        
        # Format and log request
        request_output = DebugFormatter.format_request(request)
        logger.debug(request_output)
        
        # Format and log response
        response_output = DebugFormatter.format_response(response)
        logger.debug(response_output)
        
        return response
    
    return debug_response_hook


def setup_debug_logging():
    """Configure logging for debug output with a clean format"""
    # Create a custom formatter that doesn't add timestamps/levels for DEBUG messages
    class CleanDebugFormatter(logging.Formatter):
        def format(self, record):
            if record.levelno == logging.DEBUG:
                # For debug messages, just return the message (no timestamp/level prefix)
                return _redact_sensitive_debug_text(record.getMessage())
            else:
                # For other levels, use standard format
                return super().format(record)
    
    # Set up the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with our clean formatter
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(CleanDebugFormatter())
    root_logger.addHandler(console_handler)
    
    # Set the gimme-aws-creds logger
    gac_logger = logging.getLogger('gimme_aws_creds')
    gac_logger.setLevel(logging.DEBUG)
