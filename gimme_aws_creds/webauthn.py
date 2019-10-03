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

import base64
from threading import Event, Thread

from fido2.client import Fido2Client, ClientError
from fido2.hid import CtapHidDevice, STATUS

from gimme_aws_creds.errors import NoFIDODeviceFoundError, FIDODeviceTimeoutError


class FakeAssertion(object):
    def __init__(self):
        self.signature = b'fake'
        self.auth_data = b'fake'


class WebAuthnClient(object):

    @staticmethod
    def _correct_padding(data):
        if len(data) % 4:
            data += '=' * (4 - len(data) % 4)
        return data    

    def __init__(self, ui, okta_org_url, challenge, credentialid):
        """
        :param okta_org_url: Base URL string for Okta IDP.
        :param challenge: Challenge
        :param credentialid: credentialid
        """
        self.ui = ui
        self._okta_org_url = okta_org_url
        self._clients = None
        self._has_prompted = False
        self._challenge = challenge
        self._cancel = Event()
        self._assertions = None
        self._client_data = None 
        self._rp = {'id': okta_org_url[8:], 'name': okta_org_url[8:]}
        self._allow_list = [{
            'type': 'public-key',
            'id': base64.urlsafe_b64decode(self._correct_padding(credentialid))
        }]

    def locate_device(self):
        # Locate a device
        devs = list(CtapHidDevice.list_devices())
        if not devs:
            self.ui.info('No FIDO device found')
            raise NoFIDODeviceFoundError

        self._clients = [Fido2Client(d, self._okta_org_url) for d in devs]

    def on_keepalive(self, status):
        if status == STATUS.UPNEEDED and not self._has_prompted:
            self.ui.info('\nTouch your authenticator device now...\n')
            self._has_prompted = True

    def work(self, client):
        try:
            self._assertions, self._client_data = client.get_assertion(
                self._rp['id'], self._challenge, self._allow_list, timeout=self._cancel, on_keepalive=self.on_keepalive
            )
        except ClientError as e:
            if e.code == ClientError.ERR.DEVICE_INELIGIBLE:
                self.ui.info('Security key is ineligible')  # TODO extract key info
                return
            elif e.code != ClientError.ERR.TIMEOUT:
                raise
            else:
                return
        self._cancel.set()

    def verify(self):
        # If authenticator is not found, prompt
        try:
            self.locate_device()
        except NoFIDODeviceFoundError:
            self.ui.input('Please insert your security key and press enter...')
            self.locate_device()

        threads = []
        for client in self._clients:
            t = Thread(target=self.work, args=(client,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if not self._cancel.is_set():
            self.ui.info('Operation timed out or no valid Security Key found !')
            raise FIDODeviceTimeoutError

        return self._client_data, self._assertions[0]