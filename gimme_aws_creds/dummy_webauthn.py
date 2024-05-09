"""
Copyright 2024-present Nike, Inc.
Licensed under the Apache License, Version 2.0 (the "License");
You may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and* limitations under the License.*
"""


from . import errors

class FakeAssertion(object):
    def __init__(self):
        self.signature = b'fake'
        self.auth_data = b'fake'


class WebAuthnClient(object):
    """ Dummy WebAuthnClient class - needed until ctap-keyring-device is updated to support Python 3.10+ on Windows"""
    def __init__(self, ui, okta_org_url, challenge, credential_id=None, timeout_ms=30_000):
        return None

    def locate_device(self):
        return None

    def on_keepalive(self, status):
        return None

    def verify(self):
        raise errors.GimmeAWSCredsError(
                "WebAuthn devices not supported on this platform", 2
            )
        
    def _verify(self, client):
        return None

    def make_credential(self, user):
        raise errors.GimmeAWSCredsError(
                "WebAuthn devices not supported on this platform", 2
            )

    def _make_credential(self, client, user):
        return None

    def _run_in_thread(self, method, *args, **kwargs):
        return None

    def _get_pin_from_client(self, client):
        raise errors.GimmeAWSCredsError(
                "WebAuthn devices not supported on this platform", 2
            )
    @staticmethod
    def _get_user_verification_requirement_from_client(client):
        raise errors.GimmeAWSCredsError(
                "WebAuthn devices not supported on this platform", 2
            )
