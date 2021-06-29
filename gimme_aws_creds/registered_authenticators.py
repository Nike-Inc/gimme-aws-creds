import hashlib
import json
import os


class RegisteredAuthenticators(object):
    """
       The RegisteredAuthenticators class manages a json file of gimme-aws-creds registered
       FIDO authenticators.

       There's a list of RegisteredAuthenticator entries with two fields:
       - cred_id_hash - sha512 of the registered credential id
       - user - a user identifier (email, name, uid, ...)
    """

    JSON_PATH_ENV_VAR = 'OKTA_REGISTERED_AUTHENTICATORS_FILE'

    def __init__(self, gac_ui):
        """
        :type gac_ui: ui.UserInterface
        """
        self.ui = gac_ui
        self._json_path = self.ui.environ.get(self.JSON_PATH_ENV_VAR,
                                              os.path.join(self.ui.HOME, '.okta_aws_registered_authenticators'))
        self._create_file_if_necessary(self._json_path)

    @staticmethod
    def _create_file_if_necessary(path):
        if os.path.exists(path):
            return None

        with open(path, 'w') as f:
            json.dump([], f)

    def add_authenticator(self, credential_id, user):
        """
        :param credential_id: the id of added authenticator credential
        :type credential_id: bytes
        :param user: a user identifier (email, name, uid, ...)
        :type user: str
        """
        authenticators = self._get_authenticators()
        authenticators.append(RegisteredAuthenticator(credential_id=credential_id, user=user))

        with open(self._json_path, 'w') as f:
            json.dump(authenticators, f)

    def get_authenticator_user(self, credential_id):
        """
        :param credential_id: the id of the authenticator's credential
        :type credential_id: bytes
        :return: user identifier, if credential id was registered by gimme-aws-creds, or None
        :rtype: str
        """
        authenticators = self._get_authenticators()
        for authenticator in authenticators:
            if authenticator.matches(credential_id):
                return authenticator.user

        return None

    def _get_authenticators(self):
        with open(self._json_path) as f:
            entries = json.load(f)
            return [RegisteredAuthenticator(**entry) for entry in entries]


class RegisteredAuthenticator(dict):
    """
    An entry in the registered authenticators json file, which holds a hashed credential id, and its user id.
    """

    def __init__(self, credential_id=None, credential_id_hash=None, user=None):
        """
        :type credential_id: bytes
        :type user: str
        """
        credential_id_hash = credential_id_hash or self._hash_credential_id(credential_id)
        super().__init__(credential_id_hash=credential_id_hash, user=user)

        self.credential_id_hash = credential_id_hash
        self.user = user

    def matches(self, credential_id):
        return self.credential_id_hash == self._hash_credential_id(credential_id)

    @staticmethod
    def _hash_credential_id(credential_id):
        return hashlib.sha512(credential_id).hexdigest()
