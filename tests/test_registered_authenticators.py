import json
import os
import unittest

from gimme_aws_creds.registered_authenticators import RegisteredAuthenticators, RegisteredAuthenticator
from tests.user_interface_mock import MockUserInterface


class TestConfig(unittest.TestCase):
    """Class to test RegisteredAuthenticators Class."""

    def setUp(self):
        """Set up for the unit tests"""
        ui_obj = MockUserInterface()
        self.registered_authenticators = RegisteredAuthenticators(ui_obj)
        self.file_path = self.registered_authenticators._json_path

    def test_file_creation_post_init(self):
        assert os.path.exists(self.file_path)

    def test_add_authenticator_sanity(self):
        cred_id, user = b'my-credential-id', 'my-user'
        self.registered_authenticators.add_authenticator(cred_id, user)

        with open(self.file_path) as f:
            data = json.load(f)

        assert len(data) == 1
        assert type(data) == list
        assert type(data[0]) == dict

        authenticator = RegisteredAuthenticator(**data[0])
        assert authenticator.user == user

    def test_get_authenticator_user_sanity(self):
        cred_id, user = b'my-credential-id', 'my-user'
        self.registered_authenticators.add_authenticator(cred_id, user)

        authenticator_user = self.registered_authenticators.get_authenticator_user(cred_id)
        assert authenticator_user == user
