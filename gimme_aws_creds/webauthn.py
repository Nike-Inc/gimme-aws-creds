"""
Copyright 2018-present SYNETIS.
Licensed under the Apache License, Version 2.0 (the "License");
You may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and* limitations under the License.*
"""

from __future__ import print_function, absolute_import, unicode_literals

from getpass import getpass
from threading import Event, Thread

from ctap_keyring_device.ctap_keyring_device import CtapKeyringDevice
from ctap_keyring_device.ctap_strucs import CtapOptions
from fido2 import cose
from fido2.client import Fido2Client, ClientError
from fido2.hid import CtapHidDevice, STATUS
from fido2.utils import websafe_decode
from fido2.webauthn import PublicKeyCredentialCreationOptions, \
    PublicKeyCredentialType, PublicKeyCredentialParameters, PublicKeyCredentialDescriptor, UserVerificationRequirement
from fido2.webauthn import PublicKeyCredentialRequestOptions

from gimme_aws_creds.errors import NoFIDODeviceFoundError, FIDODeviceTimeoutError


class FakeAssertion(object):
    def __init__(self):
        self.signature = b'fake'
        self.auth_data = b'fake'


class WebAuthnClient(object):
    def __init__(self, ui, okta_org_url, challenge, credential_id=None, timeout_ms=30_000):
        """
        :param okta_org_url: Base URL string for Okta IDP.
        :param challenge: Challenge
        :param credential_id: FIDO credential ID
        """
        self.ui = ui
        self._okta_org_url = okta_org_url
        self._clients = None
        self._has_prompted = False
        self._challenge = websafe_decode(challenge)
        self._timeout_ms = timeout_ms
        self._event = Event()
        self._assertions = None
        self._client_data = None
        self._rp = {'id': okta_org_url[8:], 'name': okta_org_url[8:]}

        if credential_id:
            self._allow_list = [
                PublicKeyCredentialDescriptor(PublicKeyCredentialType.PUBLIC_KEY, websafe_decode(credential_id))
            ]

    def locate_device(self):
        # Locate a device
        devs = list(CtapHidDevice.list_devices())
        if not devs:
            devs = CtapKeyringDevice.list_devices()

        self._clients = [Fido2Client(d, self._okta_org_url) for d in devs]

    def on_keepalive(self, status):
        if status == STATUS.UPNEEDED and not self._has_prompted:
            self.ui.info('\nTouch your authenticator device now...\n')
            self._has_prompted = True

    def verify(self):
        self._run_in_thread(self._verify)
        return self._client_data, self._assertions[0]

    def _verify(self, client):
        try:
            user_verification = self._get_user_verification_requirement_from_client(client)
            options = PublicKeyCredentialRequestOptions(challenge=self._challenge, rp_id=self._rp['id'],
                                                        allow_credentials=self._allow_list, timeout=self._timeout_ms,
                                                        user_verification=user_verification)

            pin = self._get_pin_from_client(client)
            assertion_selection = client.get_assertion(options, event=self._event,
                                                       on_keepalive=self.on_keepalive,
                                                       pin=pin)
            self._assertions = assertion_selection.get_assertions()
            assert len(self._assertions) >= 0

            assertion_res = assertion_selection.get_response(0)
            self._client_data = assertion_res.client_data
            self._event.set()
        except ClientError as e:
            if e.code == ClientError.ERR.DEVICE_INELIGIBLE:
                self.ui.info('Security key is ineligible')  # TODO extract key info
                return

            elif e.code != ClientError.ERR.TIMEOUT:
                raise

            else:
                return

    def make_credential(self, user):
        self._run_in_thread(self._make_credential, user)
        return self._client_data, self._attestation.with_string_keys()

    def _make_credential(self, client, user):
        pub_key_cred_params = [PublicKeyCredentialParameters(PublicKeyCredentialType.PUBLIC_KEY, cose.ES256.ALGORITHM)]
        options = PublicKeyCredentialCreationOptions(self._rp, user, self._challenge, pub_key_cred_params,
                                                     timeout=self._timeout_ms)

        pin = self._get_pin_from_client(client)
        attestation_res = client.make_credential(options, event=self._event,
                                                 on_keepalive=self.on_keepalive,
                                                 pin=pin)

        self._attestation, self._client_data = attestation_res.attestation_object, attestation_res.client_data
        self._event.set()

    def _run_in_thread(self, method, *args, **kwargs):
        # If authenticator is not found, prompt
        try:
            self.locate_device()
        except NoFIDODeviceFoundError:
            self.ui.input('Please insert your security key and press enter...')
            self.locate_device()

        threads = []
        for client in self._clients:
            t = Thread(target=method, args=(client,) + args, kwargs=kwargs)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if not self._event.is_set():
            self.ui.info('Operation timed out or no valid Security Key found !')
            raise FIDODeviceTimeoutError

    @staticmethod
    def _get_pin_from_client(client):
        if not client.info.options.get(CtapOptions.CLIENT_PIN):
            return None

        # Prompt for PIN if needed
        pin = getpass("Please enter PIN: ")
        return pin

    @staticmethod
    def _get_user_verification_requirement_from_client(client):
        if not client.info.options.get(CtapOptions.USER_VERIFICATION):
            return None

        return UserVerificationRequirement.PREFERRED
