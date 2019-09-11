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

import sys
import base64
import time
import json

from fido2.hid import CtapHidDevice, STATUS
from fido2.client import ClientError
from fido2.client import Fido2Client
from threading import Event, Thread
from fido2.utils import sha256
from fido2.ctap1 import CTAP1
from fido2.ctap1 import ApduError
from fido2.ctap1 import APDU
from gimme_aws_creds.common import NoFIDODeviceFoundError, FIDODeviceTimeoutError, FIDODeviceError

class FactorU2F(object):

    def __init__(self, appId, nonce, credentialId):
        """
        :param appId: Base URL string for Okta IDP e.g. https://xxxx.okta.com'
        :param nonce: nonce
        :param credentialid: credentialid
        """
        self._clients = None
        self._has_prompted = False
        self._cancel = Event()
        self._credentialId = base64.urlsafe_b64decode(credentialId)
        self._appId = sha256(appId.encode())
        self._version = 'U2F_V2'
        self._signature = None
        self._clientData = json.dumps({
            "challenge": nonce,
            "origin": appId,
            "typ":"navigator.id.getAssertion"
        }).encode()
        self._nonce = sha256(self._clientData)

    def locate_device(self):
        # Locate a device
        devs = list(CtapHidDevice.list_devices())
        if not devs:
            print('No FIDO device found', file=sys.stderr)
            raise NoFIDODeviceFoundError

        self._clients = [CTAP1(d) for d in devs]

    def work(self, client):
        for _ in range(30):
            try:
                self._signature = client.authenticate(
                    self._nonce, self._appId, self._credentialId )
            except ApduError as e:
                if e.code == APDU.USE_NOT_SATISFIED:
                    if not self._has_prompted:
                        print('\nTouch your authenticator device now...\n', file=sys.stderr)
                        self._has_prompted = True
                    time.sleep(0.5)
                    continue
                else:
                    raise FIDODeviceError
            break

        if self._signature == None:
            raise FIDODeviceError

        self._cancel.set()

    def verify(self):
        # If authenticator is not found, prompt
        try:
            self.locate_device()
        except NoFIDODeviceFoundError:
            print('Please insert your security key and press enter...', file=sys.stderr)
            input()
            self.locate_device()

        threads = []
        for client in self._clients:
            t = Thread(target=self.work, args=(client,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if not self._cancel.is_set():
            print('Operation timed out or no valid Security Key found !', file=sys.stderr)
            raise FIDODeviceTimeoutError

        return self._clientData, self._signature