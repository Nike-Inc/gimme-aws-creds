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
    """Build an argparse.Namespace with sensible defaults for Config tests."""
    defaults = dict(
        username=None,
        profile=None,
        insecure=False,
        resolve=None,
        mfa_code=None,
        remember_device=False,
        output_format=None,
        roles=None,
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
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)
