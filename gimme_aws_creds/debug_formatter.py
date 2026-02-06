"""
Debug formatting utilities for gimme-aws-creds.
Provides clean, readable output for HTTP request/response debugging.
"""
import json
import logging
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
    
    # Sensitive fields that should be masked
    SENSITIVE_FIELDS = [
        'password', 'access_token', 'id_token', 'sessionToken',
        'stateToken', 'device_code', 'client_secret', 'SAMLResponse',
        'passCode', 'Authorization', 'Cookie', 'Set-Cookie'
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
        lines.append(f"  {cls.BOLD}{request.method}{cls.RESET} {cls.BLUE}{request.url}{cls.RESET}")
        
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
            masked_json = cls._mask_sensitive_dict(response_json)
            body_str = json.dumps(masked_json, indent=2)
            for line in body_str.split('\n'):
                lines.append(f"    {line}")
        except (json.JSONDecodeError, ValueError):
            body = response.text[:500] + "..." if len(response.text) > 500 else response.text
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
            masked = cls._mask_sensitive_dict(parsed)
            return json.dumps(masked, indent=2)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            # Return as-is if not JSON, truncated if too long
            body_str = str(body)
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
                    if value and len(str(value)) > 10 and key != 'password':
                        result[key] = str(value)[:10] + "...[MASKED]"
                    elif value:
                        result[key] = "[MASKED]"
                    else:
                        result[key] = value
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
                    result[key] = str(value)[:20] + "...[MASKED]"
                elif value:
                    result[key] = "[MASKED]"
                else:
                    result[key] = value
            else:
                result[key] = value
        return result


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
                return record.getMessage()
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
    
    # Enable debug logging for requests/urllib3 but at INFO level to reduce noise
    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger('requests').setLevel(logging.INFO)
