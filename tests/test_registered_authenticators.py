import hashlib
import unittest

from gimme_aws_creds import ui
from gimme_aws_creds.registered_authenticators import RegisteredAuthenticators


# noinspection SqlDialectInspection,SqlNoDataSourceInspection
class TestConfig(unittest.TestCase):
    """Class to test RegisteredAuthenticators Class."""

    def setUp(self):
        """Set up for the unit tests"""
        ui_obj = ui.UserInterface(environ={RegisteredAuthenticators.DB_PATH_ENV_VAR: ':memory:'})
        self.registered_authenticators = RegisteredAuthenticators(ui_obj)
        self.con = self.registered_authenticators._con

    def tearDown(self) -> None:
        self.con.close()

    def test_table_creation_post_init(self):
        cur = self.con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchone()
        assert 'registered_authenticators' in tables

    def test_add_authenticator_sanity(self):
        cred_id, user = b'my-credential-id', 'my-user'
        self.registered_authenticators.add_authenticator(cred_id, user)

        cur = self.con.execute("SELECT * from registered_authenticators")
        rows = cur.fetchall()
        assert len(rows) == 1

        row = rows[0]
        assert row[0] == hashlib.sha512(cred_id).hexdigest()
        assert row[1] == user

    def test_get_authenticator_user_sanity(self):
        cred_id, user = b'my-credential-id', 'my-user'
        self.registered_authenticators.add_authenticator(cred_id, user)

        authenticator_user = self.registered_authenticators.get_authenticator_user(cred_id)
        assert authenticator_user == user
