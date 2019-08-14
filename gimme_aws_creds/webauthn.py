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

from fido2.hid import CtapHidDevice, STATUS
from fido2.client import Fido2Client, ClientError
from threading import Event, Thread

class WebAuthnClient(object):

    def __init__(self, okta_org_url, challenge, credentialid, verify_ssl_certs=True):
        """
        :param okta_org_url: Base URL string for Okta IDP.
        :param verify_ssl_certs: Enable/disable SSL verification
        """
        self._okta_org_url = okta_org_url
        self._verify_ssl_certs = verify_ssl_certs

        if verify_ssl_certs is False:
            requests.packages.urllib3.disable_warnings()

        self._clients = None
        self._has_prompted = False
        self._challenge = challenge
        self._cancel = Event()
        self._assertions = None
        self._client_data = None 
        self._rp = {'id': okta_org_url[8:], 'name': okta_org_url[8:]}
        self._allow_list = [{
            'type': 'public-key',
            'id': base64.urlsafe_b64decode(credentialid)
        }]

    def localte_device(self):
        # Locate a device
        devs = list(CtapHidDevice.list_devices())
        if not devs:
            print('No FIDO device found')

        self._clients = [Fido2Client(d, self._okta_org_url) for d in devs]
        print(len(self._clients))

    def on_keepalive(self, status):
        if status == STATUS.UPNEEDED and not self._has_prompted:
            print('\nTouch your authenticator device now...\n')
            self._has_prompted = True

    def work(self, client):
        try:
            self._assertions, self._client_data = client.get_assertion(
                self._rp['id'], self._challenge, self._allow_list, timeout=self._cancel, on_keepalive=self.on_keepalive
            )
        except ClientError as e:
            if e.code != ClientError.ERR.TIMEOUT:
                raise
            else:
                return
        self._cancel.set()
        print('New credential created!')
        print('CIENT DATA:', self._client_data)
        print()
        print('ASSERTION DATA:', self._assertions[0])
        print('ASSERTION DATA:', self._assertions[0].auth_data)
        print('ASSERTION DATA:', base64.b64encode(self._assertions[0].auth_data.rp_id_hash).decode('utf-8'))
        

    def verify(self):
        threads = []
        for client in self._clients:
            t = Thread(target=self.work, args=(client,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if not self._cancel.is_set():
            print('Operation timed out!')

        return self._client_data, self._assertions[0]




