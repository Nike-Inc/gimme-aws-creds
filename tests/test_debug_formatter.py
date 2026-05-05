"""Unit tests for gimme_aws_creds.debug_formatter (--debug output helpers).

Covers:
  - _mask_config_value: masking of sensitive keys, pass-through of normal
    values, and edge cases (None, empty string, False).
  - _config_attr_source: how Config-object attributes are mapped to a source
    label (cli flag, env var, default).
  - format_resolved_configuration: the rendered --debug output structure.
  - setup_debug_logging: third-party noise suppression.
"""
import io
import logging
import unittest
from unittest.mock import patch

from gimme_aws_creds.config import Config
from gimme_aws_creds.debug_formatter import (
    DebugFormatter,
    _config_attr_source,
    _mask_config_value,
    format_resolved_configuration,
    setup_debug_logging,
)
from tests.helpers import make_args
from tests.user_interface_mock import MockUserInterface


class TestMaskConfigValue(unittest.TestCase):
    """Tests for _mask_config_value (sensitive value masking)."""

    def test_none_passes_through(self):
        self.assertIsNone(_mask_config_value('password', None))

    def test_empty_string_passes_through(self):
        self.assertEqual(_mask_config_value('password', ''), '')

    def test_false_passes_through(self):
        self.assertEqual(_mask_config_value('password', False), False)

    def test_non_sensitive_key_passes_through(self):
        self.assertEqual(_mask_config_value('client_id', 'abc123'), 'abc123')
        self.assertEqual(_mask_config_value('okta_org_url', 'https://x'), 'https://x')

    def test_password_is_REDACTED(self):
        result = _mask_config_value('okta_password', 'mypassword12345')
        self.assertIn('[REDACTED]', result)
        # Long values keep first 4 chars as a fingerprint
        self.assertTrue(result.startswith('mypa'))

    def test_short_value_fully_REDACTED(self):
        result = _mask_config_value('password', 'short')
        self.assertEqual(result, '[REDACTED]')

    def test_token_keys_are_REDACTED(self):
        # The keys in `_SENSITIVE_CONFIG_SUBSTRINGS` should all trigger masking
        for key in (
            'device_token', 'OKTA_API_KEY', 'api_key',
        ):
            with self.subTest(key=key):
                result = _mask_config_value(key, 'verysecretvalue123')
                self.assertIn('[REDACTED]', result, f'Key {key!r} should be REDACTED')

    def test_case_insensitive_match(self):
        result = _mask_config_value('OKTA_PASSWORD', 'topsecret123')
        self.assertIn('[REDACTED]', result)


class TestConfigAttrSource(unittest.TestCase):
    """Tests for _config_attr_source (per-attribute source label)."""

    def _make_config(self, environ=None, argv=None):
        test_ui = MockUserInterface(environ=environ or {}, argv=argv or [])
        return Config(gac_ui=test_ui, create_config=False)

    def test_default_when_nothing_set(self):
        config = self._make_config()
        self.assertEqual(_config_attr_source(config, 'verify_ssl_certs', {}), 'default')

    def test_insecure_cli_flag_marks_verify_ssl_as_cli(self):
        with patch(
            'argparse.ArgumentParser.parse_args',
            return_value=make_args(insecure=True),
        ):
            config = self._make_config()
            config.get_args()
        self.assertEqual(
            _config_attr_source(config, 'verify_ssl_certs', {}),
            'cli: --insecure',
        )

    def test_okta_config_env_var_marks_path_as_env(self):
        config = self._make_config(environ={'OKTA_CONFIG': '/tmp/x.ini'})
        self.assertEqual(
            _config_attr_source(config, 'OKTA_CONFIG', config._env_used_in_init),
            'env: OKTA_CONFIG',
        )

    def test_username_cli_takes_precedence_over_env(self):
        with patch(
            'argparse.ArgumentParser.parse_args',
            return_value=make_args(username='cli_user'),
        ):
            config = self._make_config(environ={'OKTA_USERNAME': 'env_user'})
            config.get_args()
        self.assertEqual(
            _config_attr_source(config, 'username', config._env_used_in_init),
            'cli: --username',
        )

    def test_username_env_only(self):
        config = self._make_config(environ={'OKTA_USERNAME': 'env_user'})
        self.assertEqual(
            _config_attr_source(config, 'username', config._env_used_in_init),
            'env: OKTA_USERNAME',
        )

    def test_username_neither_cli_nor_env(self):
        config = self._make_config()
        self.assertEqual(
            _config_attr_source(config, 'username', config._env_used_in_init),
            'default/unset',
        )

    def test_api_key_env_only(self):
        config = self._make_config(environ={'OKTA_API_KEY': 'k'})
        self.assertEqual(
            _config_attr_source(config, 'api_key', config._env_used_in_init),
            'env: OKTA_API_KEY',
        )

    def test_debug_cli_flag(self):
        with patch(
            'argparse.ArgumentParser.parse_args',
            return_value=make_args(debug=True),
        ):
            config = self._make_config()
            config.get_args()
        self.assertEqual(
            _config_attr_source(config, 'debug', {}),
            'cli: --debug',
        )

    def test_aws_cred_profile_cli_flag(self):
        with patch(
            'argparse.ArgumentParser.parse_args',
            return_value=make_args(aws_cred_profile='myprof'),
        ):
            config = self._make_config()
            config.get_args()
        self.assertEqual(
            _config_attr_source(config, 'cred_profile', {}),
            'cli: --aws-cred-profile',
        )


class TestFormatResolvedConfiguration(unittest.TestCase):
    """Tests for format_resolved_configuration (full --debug output)."""

    def _build_config(self, conf_file_contents, environ=None, argv=None,
                      profile='myprofile'):
        environ = environ or {}
        argv = argv or ['--profile', profile]
        test_ui = MockUserInterface(environ=environ, argv=argv)
        with open(test_ui.HOME + '/.okta_aws_login_config', 'w') as f:
            f.write(conf_file_contents)
        config = Config(gac_ui=test_ui, create_config=False)
        config.conf_profile = profile
        conf_dict = config.get_config_dict()
        return config, conf_dict

    def test_section_headers_present(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
        )
        out = format_resolved_configuration(config, conf_dict)
        self.assertIn('RESOLVED CONFIGURATION', out)
        self.assertIn('Configuration file:', out)
        self.assertIn('Active profile:', out)
        self.assertIn('Effective profile config (merged conf_dict):', out)
        self.assertIn('Config object (CLI/env/runtime values):', out)

    def test_default_config_file_path_label(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
        )
        out = format_resolved_configuration(config, conf_dict)
        self.assertIn('default location', out)
        self.assertNotIn('env: OKTA_CONFIG', out)

    def test_env_okta_config_path_label(self):
        # MockUserInterface.HOME is a fresh tempdir. Putting OKTA_CONFIG
        # there means it's set via env, even if path is conventional.
        test_ui = MockUserInterface(argv=['--profile', 'myprofile'])
        cfg_path = test_ui.HOME + '/custom.ini'
        with open(cfg_path, 'w') as f:
            f.write("[myprofile]\nclient_id = foo\n")
        # Re-build env-aware UI
        test_ui2 = MockUserInterface(
            environ={'OKTA_CONFIG': cfg_path},
            argv=['--profile', 'myprofile'],
        )
        # Reuse the config file already on disk under test_ui2.HOME? Not
        # quite - env points to the original cfg_path.
        config = Config(gac_ui=test_ui2, create_config=False)
        config.conf_profile = 'myprofile'
        conf_dict = config.get_config_dict()

        out = format_resolved_configuration(config, conf_dict)
        self.assertIn('env: OKTA_CONFIG', out)

    def test_inheritance_chain_rendered_when_inheriting(self):
        config, conf_dict = self._build_config("""
[mybase]
client_id = base_id
[myprofile]
inherits = mybase
aws_appname = MyApp
""")
        out = format_resolved_configuration(config, conf_dict)
        self.assertIn('Inheritance chain:', out)
        self.assertIn('myprofile', out)
        self.assertIn('mybase', out)
        # 'profile: mybase' tags client_id from the parent
        self.assertIn('profile: mybase', out)
        # 'profile: myprofile' tags aws_appname (defined only in child)
        self.assertIn('profile: myprofile', out)

    def test_inheritance_chain_omitted_for_simple_profile(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
        )
        out = format_resolved_configuration(config, conf_dict)
        # Only one profile means no chain to display
        self.assertNotIn('Inheritance chain:', out)

    def test_cli_args_provided_section_lists_overrides(self):
        """Provided CLI flags appear with -- prefix and value."""
        with patch(
            'argparse.ArgumentParser.parse_args',
            return_value=make_args(debug=True, profile='myprofile'),
        ):
            config, conf_dict = self._build_config(
                "[myprofile]\nclient_id = foo\n",
            )
            config.get_args()

        out = format_resolved_configuration(config, conf_dict)
        self.assertIn('CLI arguments provided:', out)
        self.assertIn('--debug', out)
        self.assertIn('--profile', out)

    def test_cli_args_section_omitted_when_no_flags(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
        )
        out = format_resolved_configuration(config, conf_dict)
        # No CLI args provided -> section should be omitted
        self.assertNotIn('CLI arguments provided:', out)

    def test_env_overrides_applied_displayed_with_source(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\nokta_username = file_user\n",
            environ={'OKTA_USERNAME': 'env_user'},
        )
        # Simulate main.py env override
        conf_dict['okta_username'] = 'env_user'
        out = format_resolved_configuration(
            config,
            conf_dict,
            env_overrides_applied={'okta_username': 'OKTA_USERNAME'},
        )
        self.assertIn('OKTA_USERNAME', out)
        # The conf_dict line for okta_username should be tagged with env source
        self.assertIn('env: OKTA_USERNAME', out)

    def test_cli_overrides_applied_tagged_in_conf_dict(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\ncred_profile = role\n",
        )
        conf_dict['cred_profile'] = 'cli-override'
        out = format_resolved_configuration(
            config,
            conf_dict,
            cli_overrides_applied={'cred_profile': '--aws-cred-profile'},
        )
        self.assertIn('cli: --aws-cred-profile', out)
        self.assertIn('cli-override', out)

    def test_sensitive_values_are_REDACTED_in_output(self):
        """Token-like values in conf_dict and env section must be REDACTED."""
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
            environ={'OKTA_DEVICE_TOKEN': 'super-secret-token-1234567890'},
        )
        conf_dict['device_token'] = 'super-secret-token-1234567890'
        out = format_resolved_configuration(
            config,
            conf_dict,
            env_overrides_applied={'device_token': 'OKTA_DEVICE_TOKEN'},
        )
        # The raw secret must NOT appear in the output
        self.assertNotIn('super-secret-token-1234567890', out)
        # But the mask marker should be present
        self.assertIn('[REDACTED]', out)

    def test_okta_password_in_conf_dict_is_REDACTED(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
        )
        conf_dict['okta_password'] = 'my-real-password'
        out = format_resolved_configuration(config, conf_dict)
        self.assertNotIn('my-real-password', out)
        self.assertIn('[REDACTED]', out)

    def test_empty_conf_dict_renders_empty_marker(self):
        config, conf_dict = self._build_config(
            "[myprofile]\nclient_id = foo\n",
        )
        out = format_resolved_configuration(config, conf_dict={})
        self.assertIn('(empty)', out)

    def test_profile_value_sources_for_nested_inheritance(self):
        config, conf_dict = self._build_config("""
[grandparent]
client_id = gp_id
[parent]
inherits = grandparent
aws_appname = ParentApp
[myprofile]
inherits = parent
aws_rolename = MyRole
""")
        out = format_resolved_configuration(config, conf_dict)
        # Each key tagged with the deepest profile that defined it
        self.assertIn('profile: grandparent', out)
        self.assertIn('profile: parent', out)
        self.assertIn('profile: myprofile', out)


class TestDebugSamlRedaction(unittest.TestCase):
    """Tests for SAML redaction in HTTP/botocore debug output."""

    def test_token_query_param_in_request_url_is_REDACTED(self):
        class Request:
            method = "GET"
            url = (
                "https://nike.okta.com/login/token/sso"
                "?token=RAW-URL-TOKEN-VALUE"
                "&fromURI=/app/UserHome"
                "&token_type=urn%3Atest"
            )
            headers = {}
            body = None

        out = DebugFormatter.format_request(Request())

        self.assertIn("token=[REDACTED]", out)
        self.assertIn("fromURI=/app/UserHome", out)
        self.assertIn("token_type=urn%3Atest", out)
        self.assertNotIn("RAW-URL-TOKEN-VALUE", out)
        self.assertNotIn("RAW-URL", out)

    def test_sensitive_json_fields_are_fully_REDACTED(self):
        out = DebugFormatter._format_body(
            """
            {
              "access_token": "RAW-ACCESS-TOKEN-VALUE",
              "profile": {
                "id_token": "RAW-ID-TOKEN-VALUE"
              },
              "items": [
                {"sessionToken": "RAW-SESSION-TOKEN-VALUE"}
              ]
            }
            """
        )

        self.assertIn('"access_token": "[REDACTED]"', out)
        self.assertIn('"id_token": "[REDACTED]"', out)
        self.assertIn('"sessionToken": "[REDACTED]"', out)
        self.assertNotIn("RAW-ACCESS", out)
        self.assertNotIn("RAW-ID", out)
        self.assertNotIn("RAW-SESSION", out)

    def test_actor_token_in_json_response_body_is_fully_REDACTED(self):
        class JsonResponse:
            status_code = 200
            reason = "OK"
            headers = {}

            def json(self):
                return {
                    "actor_token": "RAW-ACTOR-TOKEN-VALUE",
                    "expires_in": 3600,
                }

        out = DebugFormatter.format_response(JsonResponse())

        self.assertIn('"actor_token": "[REDACTED]"', out)
        self.assertIn('"expires_in": 3600', out)
        self.assertNotIn("RAW-ACTOR-TOKEN-VALUE", out)
        self.assertNotIn("RAW-ACTOR", out)

    def test_oauth_exchange_tokens_in_form_encoded_request_body_are_fully_REDACTED(self):
        body = (
            "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Atoken-exchange"
            "&actor_token=RAW-ACTOR-TOKEN-VALUE"
            "&subject_token=RAW-SUBJECT-TOKEN-VALUE"
            "&actor_token_type=urn%3Aietf%3Aparams%3Aoauth%3Atoken-type%3Aaccess_token"
            "&subject_token_type=urn%3Aietf%3Aparams%3Aoauth%3Atoken-type%3Aaccess_token"
        )

        out = DebugFormatter._format_body(body)

        self.assertIn("actor_token=[REDACTED]", out)
        self.assertIn("subject_token=[REDACTED]", out)
        self.assertIn("actor_token_type=", out)
        self.assertIn("subject_token_type=", out)
        self.assertNotIn("RAW-ACTOR-TOKEN-VALUE", out)
        self.assertNotIn("RAW-SUBJECT-TOKEN-VALUE", out)
        self.assertNotIn("RAW-ACTOR", out)
        self.assertNotIn("RAW-SUBJECT", out)

    def test_form_encoded_assume_role_request_preserves_operation_name(self):
        body = (
            "Action=AssumeRoleWithSAML&Version=2011-06-15"
            "&SAMLAssertion=RAW-SAML-ASSERTION-TOKEN"
            "&RoleArn=arn:aws:iam::123456789012:role/test"
        )

        out = DebugFormatter._format_body(body)

        self.assertIn("Action=AssumeRoleWithSAML", out)
        self.assertIn("SAMLAssertion=[REDACTED]", out)
        self.assertNotIn("RAW-SAML-ASSERTION-TOKEN", out)

    def test_assume_role_with_saml_response_body_is_redacted(self):
        class PlainTextResponse:
            status_code = 200
            reason = "OK"
            headers = {}
            text = (
                "<AssumeRoleWithSAMLResponse>"
                "<AssumeRoleWithSAMLResult>"
                "<Credentials><SecretAccessKey>RAW-SECRET</SecretAccessKey></Credentials>"
                "</AssumeRoleWithSAMLResult>"
                "</AssumeRoleWithSAMLResponse>"
            )

            def json(self):
                raise ValueError

        out = DebugFormatter.format_response(PlainTextResponse())

        self.assertIn("AWS STS SAML response redacted", out)
        self.assertNotIn("RAW-SECRET", out)
        self.assertNotIn("AssumeRoleWithSAMLResponse", out)

    def test_setup_debug_logging_redacts_botocore_saml_values(self):
        root_logger = logging.getLogger()
        gac_logger = logging.getLogger('gimme_aws_creds')
        old_handlers = root_logger.handlers[:]
        old_level = root_logger.level
        old_gac_level = gac_logger.level
        stream = io.StringIO()

        try:
            with patch('sys.stderr', stream):
                setup_debug_logging()
                logging.getLogger('botocore.endpoint').debug(
                    "Making request for %s with params: %s",
                    "OperationModel(name=AssumeRoleWithSAML)",
                    {
                        "body": {
                            "Action": "AssumeRoleWithSAML",
                            "SAMLAssertion": "RAW-SAML-ASSERTION-TOKEN",
                        },
                    },
                )
                logging.getLogger('botocore.parsers').debug(
                    "Response body:\n%s",
                    "b'<AssumeRoleWithSAMLResponse>RAW-RESPONSE</AssumeRoleWithSAMLResponse>'",
                )
        finally:
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            for handler in old_handlers:
                root_logger.addHandler(handler)
            root_logger.setLevel(old_level)
            gac_logger.setLevel(old_gac_level)

        out = stream.getvalue()
        self.assertIn("OperationModel(name=AssumeRoleWithSAML)", out)
        self.assertIn("Action': 'AssumeRoleWithSAML", out)
        self.assertNotIn("RAW-SAML-ASSERTION-TOKEN", out)
        self.assertNotIn("RAW-RESPONSE", out)
        self.assertNotIn("AssumeRoleWithSAMLResponse", out)


if __name__ == '__main__':
    unittest.main()
