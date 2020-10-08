import hashlib
import os
import sqlite3

from fido2.utils import websafe_decode


# noinspection SqlDialectInspection,SqlNoDataSourceInspection
class RegisteredAuthenticators(object):
    """
       The RegisteredAuthenticators Class manages a sqlite DB for gimme-aws-creds registered
       FIDO authenticators.

       There's a single table: registered authenticators, with two columns:
       - cred_id_hash - sha512 of the registered credential id
       - user - a user identifier (email, name, uid, ...)
    """

    DB_PATH_ENV_VAR = 'OKTA_REGISTERED_AUTHENTICATORS_DB'

    def __init__(self, gac_ui):
        """
        :type gac_ui: ui.UserInterface
        """
        self.ui = gac_ui
        self._db_path = self.ui.environ.get(self.DB_PATH_ENV_VAR,
                                            os.path.join(self.ui.HOME, '.okta_aws_registered_authenticators'))
        self._con = sqlite3.connect(self._db_path)
        self._create_authenticators_table()

    def _create_authenticators_table(self):
        with self._con:
            self._con.execute('CREATE TABLE IF NOT EXISTS registered_authenticators '
                              '(cred_id_hash TEXT NOT NULL, user TEXT NOT NULL);')

    def add_authenticator(self, credential_id, user):
        """
        :param credential_id: the id of added authenticator credential
        :type credential_id: str or bytes
        :param user: a user identifier (email, name, uid, ...)
        :type user: str
        """
        with self._con:
            credential_id_hash = hashlib.sha512(credential_id).hexdigest()
            self._con.execute('INSERT INTO registered_authenticators VALUES (?, ?)', (credential_id_hash, user))

    def get_authenticator_user(self, b64_encoded_credential_id):
        """
        :param b64_encoded_credential_id: urlsafe base64 credential id
        :type b64_encoded_credential_id: str
        :return: user identifier, if credential id was registered by gimme-aws-creds, or None
        :rtype: str
        """
        with self._con:
            credential_id = websafe_decode(b64_encoded_credential_id)
            credential_id_hash = hashlib.sha512(credential_id).hexdigest()
            cur = self._con.execute('SELECT user FROM registered_authenticators WHERE cred_id_hash=?',
                                    (credential_id_hash,))
            column = cur.fetchone()
            if column:
                return column[0]

            return None
