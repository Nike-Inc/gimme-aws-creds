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

import pwinput
import humps

from threading import Event, Thread

from ctap_keyring_device.ctap_keyring_device import CtapKeyringDevice
from ctap_keyring_device.ctap_strucs import CtapOptions
from fido2.client import Fido2Client, ClientError, UserInteraction
from fido2.ctap2.pin import ClientPin
from fido2.hid import CtapHidDevice
from fido2.utils import websafe_decode
from fido2.webauthn import PublicKeyCredentialCreationOptions, \
    PublicKeyCredentialType, PublicKeyCredentialParameters, PublicKeyCredentialDescriptor, UserVerificationRequirement, \
    PublicKeyCredentialUserEntity, AuthenticatorSelectionCriteria
from fido2.webauthn import PublicKeyCredentialRequestOptions
from typing import Optional

from gimme_aws_creds.errors import NoFIDODeviceFoundError, FIDODeviceTimeoutError, NoEligibleFIDODeviceFoundError, FIDODeviceError


class UI(UserInteraction):
    def __init__(self, ui):
        self.ui = ui
        self._has_prompted = False
        self._prompt_text = ""

    def set_prompt_text(self, text):
        self._prompt_text = text

    def prompt_up(self) -> None:
        if not self._has_prompted:
            self.ui.info('\nTouch your {} now...\n'.format(self._prompt_text))
            self._has_prompted = True

    def request_pin(
        self, permissions: ClientPin.PERMISSION, rp_id: Optional[str]
    ) -> Optional[str]:
        """Called when the client requires a PIN from the user.

        Should return a PIN, or None/Empty to cancel."""
        return pwinput.pwinput("Please enter PIN: ")

    def request_uv(
        self, permissions: ClientPin.PERMISSION, rp_id: Optional[str]
    ) -> bool:
        """Called when the client is about to request UV from the user.

        Should return True if allowed, or False to cancel."""
        self.ui.info("User Verification requested.")
        return True


class WebAuthnClient(object):
    def __init__(self, ui, okta_org_url, challenge, credential_id=None, timeout_ms=30_000):
        """
        :param okta_org_url: Base URL string for Okta IDP.
        :param challenge: Challenge
        :param credential_id: FIDO credential ID, or list of FIDO credential IDs.
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
        self._allow_list = []
        self._exception = None
        self.user_interaction = UI(ui=ui)

        if credential_id:
            if type(credential_id) is list:
                for id in credential_id:
                    self._allow_list.append(PublicKeyCredentialDescriptor(PublicKeyCredentialType.PUBLIC_KEY, websafe_decode(id)))
            else:
                self._allow_list = [
                    PublicKeyCredentialDescriptor(PublicKeyCredentialType.PUBLIC_KEY, websafe_decode(credential_id))
                ]

    def locate_device(self):
        # Locate a device
        devs = list(CtapHidDevice.list_devices())
        try:
            devs += list(CtapKeyringDevice.list_devices())
        except (TypeError, ValueError):
            self.ui.info("PR not yet merged, keyring devices will not be found.  https://github.com/dany74q/ctap-keyring-device/pull/10")

        self._clients = [Fido2Client(device=d, origin=self._okta_org_url, user_interaction=self.user_interaction) for d in devs]

    def verify(self):
        self.user_interaction.set_prompt_text("registered authentication device")
        self._run_in_thread(self._verify)
        return self._client_data, self._assertions[0]

    def _verify(self, client):
        try:
            user_verification = self._get_user_verification_requirement_from_client(client)
            options = PublicKeyCredentialRequestOptions(challenge=self._challenge, rp_id=self._rp['id'],
                                                        allow_credentials=self._allow_list, timeout=self._timeout_ms,
                                                        user_verification=user_verification)

            assertion_selection = client.get_assertion(options, event=self._event)
            self.ui.info('Processing...\n')
            self._assertions = assertion_selection.get_assertions()
            if len(self._assertions) < 0:
                self._exception.append(RuntimeError("No assertions from key."))
                return

            assertion_res = assertion_selection.get_response(0)
            self._client_data = assertion_res.client_data
            self._event.set()
        except ClientError as e:
            if e.code == ClientError.ERR.DEVICE_INELIGIBLE:
                self.ui.info('Security key is ineligible: {}\n'.format(e.cause))
                self._exception.append(NoEligibleFIDODeviceFoundError("Security key is ineligible: {}".format(e.cause)))
                return

            elif e.code != ClientError.ERR.TIMEOUT:
                self._exception.append(e)
                return

            else:
                return

    def make_credential(self, activation):
        self.user_interaction.set_prompt_text("new authentication device")
        self._run_in_thread(self._make_credential, activation)
        return self._client_data, self._attestation

    def _make_credential(self, client, activation):
        # Generate the list of acceptable key parameters from the Okta JSON.
        pub_key_cred_params = []
        for param in activation['pubKeyCredParams']:
            pub_key_cred_params.append(PublicKeyCredentialParameters(**param))

        # Generate the list of excluded key IDs, if any, from the Okta JSON.
        # This will generally include all currently enrolled keys.
        exclude = []
        for id in activation['excludeCredentials']:
            exclude.append(PublicKeyCredentialDescriptor(id['type'], websafe_decode(id['id'])))

        # Generate the user entity from the Okta JSON.
        # Note:
        # display_name has a different name in the JSON, I'm not sure if it can be absent entirely.
        # id must be converted to bytes, not passed directly, otherwise things will fail.
        user_json = humps.decamelize(activation['user'])
        user_json['id'] = bytes(user_json['id'], encoding='utf-8')
        user = PublicKeyCredentialUserEntity(**user_json)

        # Generate the authn selection from the Okta JSON, decamelized.
        selection_json = humps.decamelize(activation['authenticatorSelection'])
        # Work around https://github.com/Yubico/python-fido2/issues/162
        if not (client.info.options.get("uv") or client.info.options.get("pinUvAuthToken")):
            selection_json['user_verification'] = None

        auth_selection = AuthenticatorSelectionCriteria(**selection_json)

        # And build the public key credential creation options.
        options = PublicKeyCredentialCreationOptions(
            rp=self._rp,
            user=user,
            challenge=self._challenge,
            pub_key_cred_params=activation['pubKeyCredParams'],
            timeout=self._timeout_ms,
            exclude_credentials=exclude,
            attestation=activation['attestation'],
            authenticator_selection=auth_selection)

        try:
            attestation_res = client.make_credential(options, event=self._event)
        except ClientError as e:
            if e.code == ClientError.ERR.DEVICE_INELIGIBLE:
                self.ui.info('Security key is ineligible: {}\n'.format(e.cause))
                self._exception.append(NoEligibleFIDODeviceFoundError("Security key is ineligible: {}".format(e.cause)))
                return
            elif e.code == ClientError.ERR.TIMEOUT:
                return
            else:
                self._exception.append(e)
                return

        self._attestation, self._client_data = attestation_res.attestation_object, attestation_res.client_data
        self._event.set()

    def _run_in_thread(self, method, *args, **kwargs):
        # If authenticator is not found, prompt
        self.locate_device()

        if self._clients == []:
            self.ui.input('Please insert your security key and press enter...')
            self.locate_device()

        if self._clients == []:
            raise NoFIDODeviceFoundError("No authentication device found.")

        self._exception = []
        threads = []
        for client in self._clients:
            t = Thread(target=method, args=(client,) + args, kwargs=kwargs)
            self.ui.info("Added client.")
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        if not self._event.is_set():
            main_error = FIDODeviceTimeoutError('Operation timed out')

            for e in self._exception:
                if isinstance(e, NoEligibleFIDODeviceFoundError) and not isinstance(main_error, FIDODeviceError):
                    main_error = NoEligibleFIDODeviceFoundError('No eligible authentication devices found.')
                elif not isinstance(e, FIDODeviceTimeoutError):
                    main_error = FIDODeviceError("Error: {}".format(e))
                    self.ui.info("Error from Webauthn key: {}".format(e))

            raise main_error

    @staticmethod
    def _get_user_verification_requirement_from_client(client):
        if not client.info.options.get(CtapOptions.USER_VERIFICATION):
            return None

        return UserVerificationRequirement.PREFERRED
