"""Shared test utilities to reduce duplication across test modules."""
import argparse
import sys
from contextlib import contextmanager
from io import StringIO


@contextmanager
def captured_output():
    """Capture stdout and stderr."""
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield new_out, new_err
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def make_args(**overrides):
    """Build an argparse.Namespace with the same defaults as the real
    argparse parser in gimme_aws_creds.config.Config.get_args().

    Important: keep these defaults synchronized with the parser. Config tracks
    which CLI flags were explicitly provided by comparing parsed values to the
    parser's defaults; mismatched defaults here would cause spurious entries
    in Config._cli_args_provided.
    """
    defaults = dict(
        # store_true flags default to False
        insecure=False,
        resolve=False,
        remember_device=False,
        action_register_device=False,
        action_configure=False,
        action_list_profiles=False,
        action_list_roles=False,
        action_store_json_creds=False,
        action_setup_fido_authenticator=False,
        open_browser=False,
        force_classic=False,
        disable_keychain=False,
        debug=False,
        enable_alicloud=False,
        # value-bearing flags default to None
        username=None,
        profile=None,
        mfa_code=None,
        output_format=None,
        roles=None,
        aws_cred_profile=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)
