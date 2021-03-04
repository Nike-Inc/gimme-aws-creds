"""Unit tests for gimme_aws_creds"""
import hashlib
import json
import sys
import unittest
from contextlib import contextmanager
from io import StringIO
from unittest.mock import patch
from urllib.parse import quote

import requests
import responses
from fido2.attestation import PackedAttestation
from fido2.ctap2 import AttestationObject, AuthenticatorData, AttestedCredentialData
from nose.tools import assert_equals

from gimme_aws_creds import errors, ui
from gimme_aws_creds.okta import OktaClient


class TestOktaClient(unittest.TestCase):
    """Class to test Okta Client Class.
       Mock is used to mock external calls"""

    @contextmanager
    def captured_output(self):
        """Capture StdErr and StdOut"""
        new_out, new_err = StringIO(), StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = new_out, new_err
            yield sys.stdout, sys.stderr
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def setUp(self):
        """Set up for the unit tests"""
        self.okta_org_url = 'https://example.okta.com'
        self.server_embed_link = 'https://example.okta.com/home/foo/bar/baz'
        self.gimme_creds_server = 'https://localhost:8443'
        self.login_url = 'https://localhost:8443/login?stateToken=00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI'
        self.state_token = '00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI'
        self.client = self.setUp_client(self.okta_org_url, False)

        self.sms_factor = {
            "id": "sms9hmdk2qvhjOQQ30h7",
            "factorType": "sms",
            "provider": "OKTA",
            "vendorName": "OKTA",
            "profile": {
                "phoneNumber": "+1 XXX-XXX-1234"
            },
            "_links": {
                "verify": {
                    "href": "https://example.okta.com/api/v1/authn/factors/sms9hmdk2qvhjOQQ30h7/verify",
                    "hints": {
                        "allow": [
                            "POST"
                        ]
                    }
                }
            }
        }

        self.push_factor = {
                "id": "opf9ei43pbAgb2qgc0h7",
                "factorType": "push",
                "provider": "OKTA",
                "vendorName": "OKTA",
                "profile": {
                    "credentialId": "jane.does@example.com",
                    "deviceType": "SmartPhone_IPhone",
                    "keys": [
                        {
                            "kty": "PKIX",
                            "use": "sig",
                            "kid": "default",
                            "x5c": [
                                "fdsfsdfdsfs"
                            ]
                        }
                    ],
                    "name": "Jane.Doe iPhone",
                    "platform": "IOS",
                    "version": "10.2.1"
                },
                "_links": {
                    "verify": {
                        "href": "https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify",
                        "hints": {
                            "allow": [
                                "POST"
                            ]
                        }
                    }
                }
            }

        self.totp_factor = {
                "id": "ost9ei4toqQBAzXmw0h7",
                "factorType": "token:software:totp",
                "provider": "OKTA",
                "vendorName": "OKTA",
                "profile": {
                    "credentialId": "jane.doe@example.com"
                },
                "_links": {
                    "verify": {
                        "href": "https://example.okta.com/api/v1/authn/factors/ost9ei4toqQBAzXmw0h7/verify",
                        "hints": {
                            "allow": [
                                "POST"
                            ]
                        }
                    }
                }
            }

        self.hardware_factor = {
                'id': 'ykfb7c5ujftQeL9B51t9',
                'factorType': 'token:hardware',
                'provider': 'YUBICO',
                'vendorName': 'YUBICO',
                'profile': {
                    'credentialId': '000009884014'
                 },
                '_links': {
                    'verify': {
                        'href': 'https://datto.okta.com/api/v1/authn/factors/ykfb0c5ujftWeL9X51t7/verify',
                        'hints': {
                            'allow': [
                                'POST'
                            ]
                        }
                    }
                }
            }

        self.unknown_factor = {
                "id": "ost9ei4toqQBAzXmw0h7",
                "factorType": "UNKNOWN_FACTOR",
                "provider": "OKTA",
                "vendorName": "OKTA"
        }

        self.webauthn_factor = {
            "id": "fw13371cpasTeNMOL4x6",
            "factorType": "webauthn",
            "provider": "FIDO",
            "vendorName": "FIDO",
            "profile": {
                "credentialId": "36Ax3uBOTSaupwEZ6Ftnz5EzGrDXI0PGqhVddg6ZlMM=",
            },
            "_links": {
                "verify": {
                    "href": "https://example.okta.com/api/v1/authn/factors/fw13371cpasTeNMOL4x6/verify",
                    "hints": {
                        "allow": [
                            "POST"
                        ]
                    }
                },
            }
        }

        self.api_results = [{
          "id": "0oaabbfwyixfM6Gwu0h7",
          "name": "Sample AWS Account",
          "identityProviderArn": "arn:aws:iam::012345678901:saml-provider/okta-sso",
          "roles": [{
              "name": "ReadOnly",
              "arn": "arn:aws:iam::012345678901:role/ReadOnly"
            },
            {
              "name": "Admin",
              "arn": "arn:aws:iam::012345678901:role/Admin"
            }
          ],
          "links": {
            "appLink": "https://example.okta.com/home/amazon_aws/0oaabbfwyixfM6Gwu0h7/137",
            "appLogo": "https://op1static.oktacdn.com/assets/img/logos/amazon-aws.0ade36569a58c5a43c01603e2d259aa9.png"
          }
        }]

        self.login_saml = """
        <html lang="en">

        <body>
          <form id="appForm" action="https&#x3a;&#x2f;&#x2f;localhost&#x3a;8443&#x2f;saml&#x2f;SSO" method="POST">
            <input name="SAMLResponse" type="hidden" value="PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4NCjxzYW1sMnA6UmVzcG9uc2UgRGVzdGluYXRpb249Imh0dHBzOi8vbG9jYWxob3N0Ojg0NDMvc2FtbC9TU08iIElEPSJpZDMyMTIwMzUzOTczODgyMDAxMTI2Mjk1MDA2Ig0KICAgIEluUmVzcG9uc2VUbz0iYTMxNjFmY2RnY2Q5Zzg4aDQxZ2phZ2IyZjg3MTdjZSIgSXNzdWVJbnN0YW50PSIyMDE3LTA2LTE2VDAwOjU4OjAyLjA1N1oiIFZlcnNpb249IjIuMCINCiAgICB4bWxuczpzYW1sMnA9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpwcm90b2NvbCI%2BDQogICAgPHNhbWwyOklzc3VlciBGb3JtYXQ9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpuYW1laWQtZm9ybWF0OmVudGl0eSINCiAgICAgICAgeG1sbnM6c2FtbDI9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iPmh0dHA6Ly93d3cub2t0YS5jb20vZXhrYXRnN3U5ZzZMSmZGclowaDc8L3NhbWwyOklzc3Vlcj4NCiAgICA8ZHM6U2lnbmF0dXJlIHhtbG5zOmRzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjIj4NCiAgICAgICAgPGRzOlNpZ25lZEluZm8%2BPGRzOkNhbm9uaWNhbGl6YXRpb25NZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzEwL3htbC1leGMtYzE0biMiLz48ZHM6U2lnbmF0dXJlTWV0aG9kIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS8wNC94bWxkc2lnLW1vcmUjcnNhLXNoYTI1NiIvPg0KICAgICAgICAgICAgPGRzOlJlZmVyZW5jZSBVUkk9IiNpZDMyMTIwMzUzOTczODgyMDAxMTI2Mjk1MDA2Ij4NCiAgICAgICAgICAgICAgICA8ZHM6VHJhbnNmb3Jtcz48ZHM6VHJhbnNmb3JtIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMC8wOS94bWxkc2lnI2VudmVsb3BlZC1zaWduYXR1cmUiLz48ZHM6VHJhbnNmb3JtIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS8xMC94bWwtZXhjLWMxNG4jIi8%2BPC9kczpUcmFuc2Zvcm1zPjxkczpEaWdlc3RNZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGVuYyNzaGEyNTYiLz4NCiAgICAgICAgICAgICAgICA8ZHM6RGlnZXN0VmFsdWU%2BZ0hJNGMrMzJFbklScU5aRzBEQ0lZWjJzQzQ3Z29lQzBzYTVWYisyOGV2MD08L2RzOkRpZ2VzdFZhbHVlPg0KICAgICAgICAgICAgPC9kczpSZWZlcmVuY2U%2BDQogICAgICAgIDwvZHM6U2lnbmVkSW5mbz4NCiAgICAgICAgPGRzOlNpZ25hdHVyZVZhbHVlPkl1ZGZGakZRNklJa0psYXpKdDl0R1V3OWs2L3lwOVNueFI4VzRWV2pPaVc4UXVLV1VGblh0VVdIS1NwQW9EanZSODcrVVRiUEd2VUZORXh2UEMzSE5wcVE1OW5IY3VzeDRWblRoTG8xMld5aG10RVBBSTlUellUNWZEWjZHQTFHWTQwNVhRaElBZzdPVGdzOUR0dldaTitVQUVWZDVySVNvUGJZZU5nbUk1VUZoOWpDSE55aTNPVzdpbk9mTjBKUXdrd3o5OHFsTGpRbEJnTWVDWGFHWFBSSVRpLzJTSHVmWW9pVUltZEZQU2hTaUlaQytZSmlDOHYxa3pRd3RDWW8vNHpmWm5WN24raXpkSWswQU52eFBHQmVIUzZ5S29ETEtwV3A0Wm13bHdFb21KdVlIVnZWVnhoaWhDeEMzTmVVbVBtRVJIYUdrMEIyZzR0T1pZVUk4QT09PC9kczpTaWduYXR1cmVWYWx1ZT4NCiAgICAgICAgPGRzOktleUluZm8%2BDQogICAgICAgICAgICA8ZHM6WDUwOURhdGE%2BDQogICAgICAgICAgICAgICAgPGRzOlg1MDlDZXJ0aWZpY2F0ZT5NSUlEbmpDQ0FvYWdBd0lCQWdJR0FWaWNuWjNQTUEwR0NTcUdTSWIzRFFFQkN3VUFNSUdQTVFzd0NRWURWUVFHRXdKVlV6RVRNQkVHDQogICAgICAgICAgICAgICAgICAgIEExVUVDQXdLUTJGc2FXWnZjbTVwWVRFV01CUUdBMVVFQnd3TlUyRnVJRVp5WVc1amFYTmpiekVOTUFzR0ExVUVDZ3dFVDJ0MFlURVUNCiAgICAgICAgICAgICAgICAgICAgTUJJR0ExVUVDd3dMVTFOUFVISnZkbWxrWlhJeEVEQU9CZ05WQkFNTUIyNXBhMlV0Y1dFeEhEQWFCZ2txaGtpRzl3MEJDUUVXRFdsdQ0KICAgICAgICAgICAgICAgICAgICBabTlBYjJ0MFlTNWpiMjB3SGhjTk1UWXhNVEkxTVRjMU1UQTFXaGNOTWpZeE1USTFNVGMxTWpBMFdqQ0JqekVMTUFrR0ExVUVCaE1DDQogICAgICAgICAgICAgICAgICAgIFZWTXhFekFSQmdOVkJBZ01Da05oYkdsbWIzSnVhV0V4RmpBVUJnTlZCQWNNRFZOaGJpQkdjbUZ1WTJselkyOHhEVEFMQmdOVkJBb00NCiAgICAgICAgICAgICAgICAgICAgQkU5cmRHRXhGREFTQmdOVkJBc01DMU5UVDFCeWIzWnBaR1Z5TVJBd0RnWURWUVFEREFkdWFXdGxMWEZoTVJ3d0dnWUpLb1pJaHZjTg0KICAgICAgICAgICAgICAgICAgICBBUWtCRmcxcGJtWnZRRzlyZEdFdVkyOXRNSUlCSWpBTkJna3Foa2lHOXcwQkFRRUZBQU9DQVE4QU1JSUJDZ0tDQVFFQWpjSUdsZnlUDQogICAgICAgICAgICAgICAgICAgIEk0VXV4ZGVpc1JUY3NwcVZRN1JJcE4vQmdkc2lTQStSZDdUQ1pjN1pFZEtoSDBwMU1PYVRqaVBXeTNNVW1VanRsWG9pdnI3YVd6OUQNCiAgICAgICAgICAgICAgICAgICAgTGhKREZrNkt0L3ZPWTdqamFRUUIzMzZBZWcvMXRZWFM1MDdFU3liRzBiSnRjcUNwNXNIcnBqUWVSdDUrK3lObUs2bUxaSEVYc0NGYg0KICAgICAgICAgICAgICAgICAgICA3Wkd0QnpOeEhYVC9wSG1aN2tXUlRTTkVhVy9lN2VwNnY4L1VtRm1zYkRyd0FOckVEVklnMGZDUnNvdGRsWkpGUjFIdWlpMkREOG4zDQogICAgICAgICAgICAgICAgICAgIGlJWHUrb3I5KzJsRDY1RWladExaWXpEcDRpNnRFeTY2MjdBM0c1K29uMHoyNmR4VXhjQ0hOenl6bmFqOHA0Y1VjWGI0SkQxa2poZ2YNCiAgICAgICAgICAgICAgICAgICAgK3R3eUJLQlBuTHp1d2UvVEI2QXJMYjYvUFpaenJRSURBUUFCTUEwR0NTcUdTSWIzRFFFQkN3VUFBNElCQVFBSGtRQUFpV04rbC81dw0KICAgICAgICAgICAgICAgICAgICBCeEMreTZjV0FoeVB2QlBHR2dES0J5R01iTXFvcytvUHBXR25RSVF6RGpSOW15UFY2U0JoTHZNUmxYVXM0dGVoT3pTR3Z5eTRLWnYrDQogICAgICAgICAgICAgICAgICAgIE1MSnBoRk9GOEQ5TTR4bVY3VU5xZEwvMXF2TWxuWDh4eDlqUGRpb3VMUlIxdmpMdDI4bitWRXhjeG9rUnZGdEd5bGp3N2NNZDlzT2kNCiAgICAgICAgICAgICAgICAgICAgN2dQWi9wV3lNTk5jRXozeEV2UGp5ZWFQZXZRZVJZeG9RQjh2WXZDVSszZTF1bFlTbUlzOUR0bWtmVXlVOGxDUVFFbzFocmkxOVpLWA0KICAgICAgICAgICAgICAgICAgICBTY2NPNVl0V3R2cTliUVYvVUJXOHF5YXFGWHd1WW81QTNTR0VaUloxUzdZZXZwOUJBUU9QNzUwNzlVNEhaZG95ektBaWhabmxHdURCDQogICAgICAgICAgICAgICAgICAgIFRJUE9YUTZPZjYrbnBFZmY2NDJ3VU1CZTwvZHM6WDUwOUNlcnRpZmljYXRlPg0KICAgICAgICAgICAgPC9kczpYNTA5RGF0YT4NCiAgICAgICAgPC9kczpLZXlJbmZvPg0KICAgIDwvZHM6U2lnbmF0dXJlPg0KICAgIDxzYW1sMnA6U3RhdHVzIHhtbG5zOnNhbWwycD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOnByb3RvY29sIj48c2FtbDJwOlN0YXR1c0NvZGUgVmFsdWU9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpzdGF0dXM6U3VjY2VzcyIvPjwvc2FtbDJwOlN0YXR1cz4NCiAgICA8c2FtbDI6QXNzZXJ0aW9uIElEPSJpZDMyMTIwMzUzOTc0MzE0NTUyMTIzMjU4OTA3IiBJc3N1ZUluc3RhbnQ9IjIwMTctMDYtMTZUMDA6NTg6MDIuMDU3WiINCiAgICAgICAgVmVyc2lvbj0iMi4wIiB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI%2BDQogICAgICAgIDxzYW1sMjpJc3N1ZXIgRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6bmFtZWlkLWZvcm1hdDplbnRpdHkiDQogICAgICAgICAgICB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI%2BaHR0cDovL3d3dy5va3RhLmNvbS9leGthdGc3dTlnNkxKZkZyWjBoNzwvc2FtbDI6SXNzdWVyPg0KICAgICAgICA8ZHM6U2lnbmF0dXJlIHhtbG5zOmRzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjIj4NCiAgICAgICAgICAgIDxkczpTaWduZWRJbmZvPjxkczpDYW5vbmljYWxpemF0aW9uTWV0aG9kIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS8xMC94bWwtZXhjLWMxNG4jIi8%2BPGRzOlNpZ25hdHVyZU1ldGhvZCBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMDQveG1sZHNpZy1tb3JlI3JzYS1zaGEyNTYiLz4NCiAgICAgICAgICAgICAgICA8ZHM6UmVmZXJlbmNlIFVSST0iI2lkMzIxMjAzNTM5NzQzMTQ1NTIxMjMyNTg5MDciPg0KICAgICAgICAgICAgICAgICAgICA8ZHM6VHJhbnNmb3Jtcz48ZHM6VHJhbnNmb3JtIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMC8wOS94bWxkc2lnI2VudmVsb3BlZC1zaWduYXR1cmUiLz48ZHM6VHJhbnNmb3JtIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS8xMC94bWwtZXhjLWMxNG4jIi8%2BPC9kczpUcmFuc2Zvcm1zPjxkczpEaWdlc3RNZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGVuYyNzaGEyNTYiLz4NCiAgICAgICAgICAgICAgICAgICAgPGRzOkRpZ2VzdFZhbHVlPnMrK2FqSDhNRlB3U2FzNTFLZ2grU2gzUnFobTM2TklQMEpWd2JMVjhqdlE9PC9kczpEaWdlc3RWYWx1ZT4NCiAgICAgICAgICAgICAgICA8L2RzOlJlZmVyZW5jZT4NCiAgICAgICAgICAgIDwvZHM6U2lnbmVkSW5mbz4NCiAgICAgICAgICAgIDxkczpTaWduYXR1cmVWYWx1ZT5VWVlXQXJSRHdEcmRtMnFwVldRSkk5UERnYVVVRXV6Zk1OQjEwditXR0JGNzFRTm1PSVR6QjlFREhqNlpyWXJobTFMdGxuL0J2cEo2d2pjbGJLb1JxRHpINHY0UGlMWE1ILytTWStVaDc2di9la0lyT1YzaURaZ2VBTWxQWjNWNHZYd1A5ZUZnM3o1ZVFhbUFGY2l2cW15UnFETUp1anBPaFo1dXdycU5qbS9nd3BQV0owSmw1RTJ2dEVNcGdtTDZYNmR3NGF6a3dySWRFN2NWeGUzZ2NsR3J1cTE3dHBJK3FQK1ByV29zRkcxV0tTbmpqUnptckVCZmJWcHFYZk43eEpFaTRWVDc1bklQQ2FSaFlCRkVBM0NRYlA2ZVEyM2JuUGZWVlB0NVZjWXhpU042Q2s3WmpjVzJwbkNjREQrVVBDMGJnWEZYZVoySFlPa1JmazF6S3c9PTwvZHM6U2lnbmF0dXJlVmFsdWU%2BDQogICAgICAgICAgICA8ZHM6S2V5SW5mbz4NCiAgICAgICAgICAgICAgICA8ZHM6WDUwOURhdGE%2BDQogICAgICAgICAgICAgICAgICAgIDxkczpYNTA5Q2VydGlmaWNhdGU%2BTUlJRG5qQ0NBb2FnQXdJQkFnSUdBVmljblozUE1BMEdDU3FHU0liM0RRRUJDd1VBTUlHUE1Rc3dDUVlEVlFRR0V3SlZVekVUTUJFRw0KICAgICAgICAgICAgICAgICAgICAgICAgQTFVRUNBd0tRMkZzYVdadmNtNXBZVEVXTUJRR0ExVUVCd3dOVTJGdUlFWnlZVzVqYVhOamJ6RU5NQXNHQTFVRUNnd0VUMnQwWVRFVQ0KICAgICAgICAgICAgICAgICAgICAgICAgTUJJR0ExVUVDd3dMVTFOUFVISnZkbWxrWlhJeEVEQU9CZ05WQkFNTUIyNXBhMlV0Y1dFeEhEQWFCZ2txaGtpRzl3MEJDUUVXRFdsdQ0KICAgICAgICAgICAgICAgICAgICAgICAgWm05QWIydDBZUzVqYjIwd0hoY05NVFl4TVRJMU1UYzFNVEExV2hjTk1qWXhNVEkxTVRjMU1qQTBXakNCanpFTE1Ba0dBMVVFQmhNQw0KICAgICAgICAgICAgICAgICAgICAgICAgVlZNeEV6QVJCZ05WQkFnTUNrTmhiR2xtYjNKdWFXRXhGakFVQmdOVkJBY01EVk5oYmlCR2NtRnVZMmx6WTI4eERUQUxCZ05WQkFvTQ0KICAgICAgICAgICAgICAgICAgICAgICAgQkU5cmRHRXhGREFTQmdOVkJBc01DMU5UVDFCeWIzWnBaR1Z5TVJBd0RnWURWUVFEREFkdWFXdGxMWEZoTVJ3d0dnWUpLb1pJaHZjTg0KICAgICAgICAgICAgICAgICAgICAgICAgQVFrQkZnMXBibVp2UUc5cmRHRXVZMjl0TUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUFqY0lHbGZ5VA0KICAgICAgICAgICAgICAgICAgICAgICAgSTRVdXhkZWlzUlRjc3BxVlE3UklwTi9CZ2RzaVNBK1JkN1RDWmM3WkVkS2hIMHAxTU9hVGppUFd5M01VbVVqdGxYb2l2cjdhV3o5RA0KICAgICAgICAgICAgICAgICAgICAgICAgTGhKREZrNkt0L3ZPWTdqamFRUUIzMzZBZWcvMXRZWFM1MDdFU3liRzBiSnRjcUNwNXNIcnBqUWVSdDUrK3lObUs2bUxaSEVYc0NGYg0KICAgICAgICAgICAgICAgICAgICAgICAgN1pHdEJ6TnhIWFQvcEhtWjdrV1JUU05FYVcvZTdlcDZ2OC9VbUZtc2JEcndBTnJFRFZJZzBmQ1Jzb3RkbFpKRlIxSHVpaTJERDhuMw0KICAgICAgICAgICAgICAgICAgICAgICAgaUlYdStvcjkrMmxENjVFaVp0TFpZekRwNGk2dEV5NjYyN0EzRzUrb24wejI2ZHhVeGNDSE56eXpuYWo4cDRjVWNYYjRKRDFramhnZg0KICAgICAgICAgICAgICAgICAgICAgICAgK3R3eUJLQlBuTHp1d2UvVEI2QXJMYjYvUFpaenJRSURBUUFCTUEwR0NTcUdTSWIzRFFFQkN3VUFBNElCQVFBSGtRQUFpV04rbC81dw0KICAgICAgICAgICAgICAgICAgICAgICAgQnhDK3k2Y1dBaHlQdkJQR0dnREtCeUdNYk1xb3Mrb1BwV0duUUlRekRqUjlteVBWNlNCaEx2TVJsWFVzNHRlaE96U0d2eXk0S1p2Kw0KICAgICAgICAgICAgICAgICAgICAgICAgTUxKcGhGT0Y4RDlNNHhtVjdVTnFkTC8xcXZNbG5YOHh4OWpQZGlvdUxSUjF2akx0MjhuK1ZFeGN4b2tSdkZ0R3lsanc3Y01kOXNPaQ0KICAgICAgICAgICAgICAgICAgICAgICAgN2dQWi9wV3lNTk5jRXozeEV2UGp5ZWFQZXZRZVJZeG9RQjh2WXZDVSszZTF1bFlTbUlzOUR0bWtmVXlVOGxDUVFFbzFocmkxOVpLWA0KICAgICAgICAgICAgICAgICAgICAgICAgU2NjTzVZdFd0dnE5YlFWL1VCVzhxeWFxRlh3dVlvNUEzU0dFWlJaMVM3WWV2cDlCQVFPUDc1MDc5VTRIWmRveXpLQWloWm5sR3VEQg0KICAgICAgICAgICAgICAgICAgICAgICAgVElQT1hRNk9mNitucEVmZjY0MndVTUJlPC9kczpYNTA5Q2VydGlmaWNhdGU%2BDQogICAgICAgICAgICAgICAgPC9kczpYNTA5RGF0YT4NCiAgICAgICAgICAgIDwvZHM6S2V5SW5mbz4NCiAgICAgICAgPC9kczpTaWduYXR1cmU%2BDQogICAgICAgIDxzYW1sMjpTdWJqZWN0IHhtbG5zOnNhbWwyPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXNzZXJ0aW9uIj4NCiAgICAgICAgICAgIDxzYW1sMjpOYW1lSUQgRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoxLjE6bmFtZWlkLWZvcm1hdDp1bnNwZWNpZmllZCI%2BamFuZS5kb2VAbmlrZS5jb208L3NhbWwyOk5hbWVJRD4NCiAgICAgICAgICAgIDxzYW1sMjpTdWJqZWN0Q29uZmlybWF0aW9uIE1ldGhvZD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmNtOmJlYXJlciI%2BPHNhbWwyOlN1YmplY3RDb25maXJtYXRpb25EYXRhIEluUmVzcG9uc2VUbz0iYTMxNjFmY2RnY2Q5Zzg4aDQxZ2phZ2IyZjg3MTdjZSINCiAgICAgICAgICAgICAgICBOb3RPbk9yQWZ0ZXI9IjIwMTctMDYtMTZUMDE6MDM6MDIuMDU3WiIgUmVjaXBpZW50PSJodHRwczovL2xvY2FsaG9zdDo4NDQzL3NhbWwvU1NPIi8%2BPC9zYW1sMjpTdWJqZWN0Q29uZmlybWF0aW9uPg0KICAgICAgICA8L3NhbWwyOlN1YmplY3Q%2BDQogICAgICAgIDxzYW1sMjpDb25kaXRpb25zIE5vdEJlZm9yZT0iMjAxNy0wNi0xNlQwMDo1MzowMi4wNThaIiBOb3RPbk9yQWZ0ZXI9IjIwMTctMDYtMTZUMDE6MDM6MDIuMDU3WiINCiAgICAgICAgICAgIHhtbG5zOnNhbWwyPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXNzZXJ0aW9uIj4NCiAgICAgICAgICAgIDxzYW1sMjpBdWRpZW5jZVJlc3RyaWN0aW9uPg0KICAgICAgICAgICAgICAgIDxzYW1sMjpBdWRpZW5jZT5jb206bmlrZTpnaW1tZV9jcmVkczpkZXY8L3NhbWwyOkF1ZGllbmNlPg0KICAgICAgICAgICAgPC9zYW1sMjpBdWRpZW5jZVJlc3RyaWN0aW9uPg0KICAgICAgICA8L3NhbWwyOkNvbmRpdGlvbnM%2BDQogICAgICAgIDxzYW1sMjpBdXRoblN0YXRlbWVudCBBdXRobkluc3RhbnQ9IjIwMTctMDYtMTZUMDA6NTg6MDIuMDU3WiINCiAgICAgICAgICAgIFNlc3Npb25JbmRleD0iYTMxNjFmY2RnY2Q5Zzg4aDQxZ2phZ2IyZjg3MTdjZSIgeG1sbnM6c2FtbDI9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iPg0KICAgICAgICAgICAgPHNhbWwyOkF1dGhuQ29udGV4dD4NCiAgICAgICAgICAgICAgICA8c2FtbDI6QXV0aG5Db250ZXh0Q2xhc3NSZWY%2BdXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFjOmNsYXNzZXM6UGFzc3dvcmRQcm90ZWN0ZWRUcmFuc3BvcnQ8L3NhbWwyOkF1dGhuQ29udGV4dENsYXNzUmVmPg0KICAgICAgICAgICAgPC9zYW1sMjpBdXRobkNvbnRleHQ%2BDQogICAgICAgIDwvc2FtbDI6QXV0aG5TdGF0ZW1lbnQ%2BDQogICAgPC9zYW1sMjpBc3NlcnRpb24%2BDQo8L3NhbWwycDpSZXNwb25zZT4%3D"
            />
            <input name="RelayState" type="hidden" value="" />
          </form>
        </body>

        </html>"""

        self.factor_list = [self.sms_factor, self.push_factor, self.totp_factor, self.webauthn_factor]

    def setUp_client(self, okta_org_url, verify_ssl_certs):
        client = OktaClient(ui.default, okta_org_url, verify_ssl_certs)
        client.req_session = requests
        return client

    def test_get_headers(self):
        """Testing that get_headers returns the expected results"""
        header = self.client._get_headers()
        self.assertEqual(header['Accept'], 'application/json')

    @responses.activate
    def test_get_state_token(self):
        """Testing state token is returned as expected"""

        auth_response = {
            "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
            "type": "SESSION_STEP_UP",
            "expiresAt": "2017-06-15T15:42:31.000Z",
            "status": "SUCCESS",
            "_embedded": {
                "user": {
                    "id": "00u8cakq7vQwtK7sR0h7",
                    "profile": {
                        "login": "Jane.Doe@example.com",
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "target": {
                    "type": "APP",
                    "name": "gimmecredsserver",
                    "label": "Gimme-Creds-Server (Dev)",
                    "_links": {
                        "logo": {
                            "name": "medium",
                            "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                            "type": "image/png"
                        }
                    }
                }
            },
            "_links": {
                "next": {
                    "name": "original",
                    "href": "https://example.okta.com/login/step-up/redirect?stateToken=00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
                    "hints": {
                        "allow": [
                            "GET"
                        ]
                    }
                }
            }
        }

        responses.add(responses.GET, self.server_embed_link, status=302, adding_headers={'Location': self.login_url})
        responses.add(responses.POST, self.okta_org_url + '/api/v1/authn', status=200, body=json.dumps(auth_response))

        self.client._server_embed_link = self.server_embed_link
        result = self.client._get_initial_flow_state(self.server_embed_link)
        self.assertEqual(result, {'stateToken': self.state_token, 'apiResponse': auth_response})

    @patch('getpass.getpass', return_value='1234qwert')
    @patch('builtins.input', return_value='ann@example.com')
    def test_get_username_password_creds(self, mock_pass, mock_input):
        """Test that initial authentication works with Okta"""
        result = self.client._get_username_password_creds()
        self.assertDictEqual(result, {'username': 'ann@example.com', 'password': '1234qwert' })

    @patch('getpass.getpass', return_value='1234qwert')
    @patch('builtins.input', return_value='')
    def test_passed_username(self, mock_pass, mock_input):
        """Test that initial authentication works with Okta"""
        self.client.set_username('ann@example.com')
        result = self.client._get_username_password_creds()
        self.assertDictEqual(result, {'username': 'ann@example.com', 'password': '1234qwert' })

#    @patch('getpass.getpass', return_value='1234qwert')
#    @patch('builtins.input', return_value='ann')
#    def test_bad_username(self, mock_pass, mock_input):
#        """Test that initial authentication works with Okta"""
#        with self.assertRaises(errors.GimmeAWSCredsExitBase):
#            self.client._get_username_password_creds()

    @patch('getpass.getpass', return_value='')
    @patch('builtins.input', return_value='ann@example.com')
    def test_missing_password(self, mock_pass, mock_input):
        """Test that initial authentication works with Okta"""
        with self.assertRaises(errors.GimmeAWSCredsExitBase):
            self.client._get_username_password_creds()

    @responses.activate
    @patch('getpass.getpass', return_value='1234qwert')
    @patch('builtins.input', return_value='ann@example.com')
    def test_login_username_password(self, mock_pass, mock_input):
        """Test that initial authentication works with Okta"""
        auth_response = {
            "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
            "type": "SESSION_STEP_UP",
            "expiresAt": "2017-06-15T15:42:31.000Z",
            "status": "SUCCESS",
            "_embedded": {
                "user": {
                    "id": "00u8cakq7vQwtK7sR0h7",
                    "profile": {
                        "login": "Jane.Doe@example.com",
                        "firstName": "Eric",
                        "lastName": "Pierce",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "target": {
                    "type": "APP",
                    "name": "gimmecredsserver",
                    "label": "Gimme-Creds-Server (Dev)",
                    "_links": {
                        "logo": {
                            "name": "medium",
                            "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                            "type": "image/png"
                        }
                    }
                }
            },
            "_links": {
                "next": {
                    "name": "original",
                    "href": "https://example.okta.com/login/step-up/redirect?stateToken=00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
                    "hints": {
                        "allow": [
                            "GET"
                        ]
                    }
                }
            }
        }

        responses.add(responses.POST, self.okta_org_url + '/api/v1/authn', status=200, body=json.dumps(auth_response))
        result = self.client._login_username_password(self.state_token, self.okta_org_url + '/api/v1/authn')
        assert_equals(result, {'stateToken': self.state_token, 'apiResponse': auth_response})

    @responses.activate
    def test_login_send_sms(self):
        """Test that SMS messages can be requested for MFA"""

        verify_response = {
            "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
            "type": "SESSION_STEP_UP",
            "expiresAt": "2017-06-15T15:06:10.000Z",
            "status": "MFA_CHALLENGE",
            "_embedded": {
                "user": {
                    "id": "00u8cakq7vQwtK7sR0h7",
                    "profile": {
                        "login": "Jane.Doe@example.com",
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "factor": {
                    "id": "sms9hmdk2qvhjOQQ30h7",
                    "factorType": "sms",
                    "provider": "OKTA",
                    "vendorName": "OKTA",
                    "profile": {
                        "phoneNumber": "+1 XXX-XXX-1234"
                    }
                },
                "policy": {
                    "allowRememberDevice": False,
                    "rememberDeviceLifetimeInMinutes": 0,
                    "rememberDeviceByDefault": False
                },
                "target": {
                    "type": "APP",
                    "name": "gimmecredsserver",
                    "label": "Gimme-Creds-Server (Dev)",
                    "_links": {
                        "logo": {
                            "name": "medium",
                            "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                            "type": "image/png"
                        }
                    }
                }
            },
            "_links": {
                "next": {
                    "name": "verify",
                    "href": "https://example.okta.com/api/v1/authn/factors/sms9hmdk2qvhjOQQ30h7/verify",
                    "hints": {
                        "allow": [
                            "POST"
                        ]
                    }
                },
                "cancel": {
                    "href": "https://example.okta.com/api/v1/authn/cancel",
                    "hints": {
                        "allow": [
                            "POST"
                        ]
                    }
                },
                "prev": {
                    "href": "https://example.okta.com/api/v1/authn/previous",
                    "hints": {
                        "allow": [
                            "POST"
                        ]
                    }
                },
                "resend": [
                    {
                        "name": "sms",
                        "href": "https://example.okta.com/api/v1/authn/factors/sms9hmdk2qvhjOQQ30h7/verify/resend",
                        "hints": {
                            "allow": [
                                "POST"
                            ]
                        }
                    }
                ]
            }
        }

        responses.add(responses.POST, 'https://example.okta.com/api/v1/authn/factors/sms9hmdk2qvhjOQQ30h7/verify', status=200, body=json.dumps(verify_response))
        result = self.client._login_send_sms(self.state_token, self.sms_factor)
        assert_equals(result, {'stateToken': self.state_token, 'apiResponse': verify_response})

    @responses.activate
    def test_login_send_push(self):
        """Test that Okta Verify can be used for MFA"""

        verify_response = {
    "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
    "type": "SESSION_STEP_UP",
    "expiresAt": "2017-06-15T22:32:40.000Z",
    "status": "MFA_CHALLENGE",
    "factorResult": "WAITING",
    "_embedded": {
        "user": {
            "id": "00u8p8560rXMQ95cP0h7",
            "profile": {
                "login": "jane.doe@example.com",
                "firstName": "Jane",
                "lastName": "Doe",
                "locale": "en",
                "timeZone": "America/Los_Angeles"
            }
        },
        "factor": {
            "id": "opf9ei43pbAgb2qgc0h7",
            "factorType": "push",
            "provider": "OKTA",
            "vendorName": "OKTA",
            "profile": {
                "credentialId": "jane.doe@example.com",
                "deviceType": "SmartPhone_IPhone",
                "keys": [
                    {
                        "kty": "PKIX",
                        "use": "sig",
                        "kid": "default",
                        "x5c": [
                            "fdsfsdfsdfsd"
                        ]
                    }
                ],
                "name": "Jane.Doe iPhone",
                "platform": "IOS",
                "version": "10.2.1"
            }
        },
        "policy": {
            "allowRememberDevice": False,
            "rememberDeviceLifetimeInMinutes": 0,
            "rememberDeviceByDefault": False
        },
        "target": {
            "type": "APP",
            "name": "gimmecredstest",
            "label": "Gimme-Creds-Test",
            "_links": {
                "logo": {
                    "name": "medium",
                    "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                    "type": "image/png"
                }
            }
        }
    },
    "_links": {
        "next": {
            "name": "poll",
            "href": "https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify",
            "hints": {
                "allow": [
                    "POST"
                ]
            }
        },
        "cancel": {
            "href": "https://example.okta.com/api/v1/authn/cancel",
            "hints": {
                "allow": [
                    "POST"
                ]
            }
        },
        "prev": {
            "href": "https://example.okta.com/api/v1/authn/previous",
            "hints": {
                "allow": [
                    "POST"
                ]
            }
        },
        "resend": [
            {
                "name": "push",
                "href": "https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify/resend",
                "hints": {
                    "allow": [
                        "POST"
                    ]
                }
            }
        ]
    }
}

        responses.add(responses.POST, 'https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify', status=200, body=json.dumps(verify_response))
        result = self.client._login_send_push(self.state_token, self.push_factor)
        assert_equals(result, {'stateToken': self.state_token, 'apiResponse': verify_response})

    @responses.activate
    @patch('getpass.getpass', return_value='1234qwert')
    def test_login_input_mfa_challenge(self, mock_pass):
        """Test that MFA works with Okta"""

        verify_response = {
            "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
            "type": "SESSION_STEP_UP",
            "expiresAt": "2017-06-15T15:07:27.000Z",
            "status": "SUCCESS",
            "_embedded": {
                "user": {
                    "id": "00u8p8560rXMQ95cP0h7",
                    "profile": {
                        "login": "jane.doe@example.com",
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "target": {
                    "type": "APP",
                    "name": "gimmecredsserver",
                    "label": "Gimme-Creds-Server (Dev)",
                    "_links": {
                        "logo": {
                            "name": "medium",
                            "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                            "type": "image/png"
                        }
                    }
                }
            },
            "_links": {
                "next": {
                    "name": "original",
                    "href": "https://example.okta.com/login/step-up/redirect?stateToken=00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
                    "hints": {
                        "allow": [
                            "GET"
                        ]
                    }
                }
            }
        }
        responses.add(responses.POST, 'https://example.okta.com/api/v1/authn/factors/sms9hmdk2qvhjOQQ30h7/verify', status=200, body=json.dumps(verify_response))
        result = self.client._login_input_mfa_challenge(self.state_token, 'https://example.okta.com/api/v1/authn/factors/sms9hmdk2qvhjOQQ30h7/verify')
        assert_equals(result, {'stateToken': self.state_token, 'apiResponse': verify_response})


    @responses.activate
    def test_check_push_result(self):
        """Test that the Okta Verify response was successful"""

        verify_response = {
    "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
    "type": "SESSION_STEP_UP",
    "expiresAt": "2017-06-15T22:32:40.000Z",
    "status": "MFA_CHALLENGE",
    "factorResult": "WAITING",
    "_embedded": {
        "user": {
            "id": "00u8p8560rXMQ95cP0h7",
            "profile": {
                "login": "jane.doe@example.com",
                "firstName": "Jane",
                "lastName": "Doe",
                "locale": "en",
                "timeZone": "America/Los_Angeles"
            }
        },
        "factor": {
            "id": "opf9ei43pbAgb2qgc0h7",
            "factorType": "push",
            "provider": "OKTA",
            "vendorName": "OKTA",
            "profile": {
                "credentialId": "jane.doe@example.com",
                "deviceType": "SmartPhone_IPhone",
                "keys": [
                    {
                        "kty": "PKIX",
                        "use": "sig",
                        "kid": "default",
                        "x5c": [
                            "fdsfsdfsdfsd"
                        ]
                    }
                ],
                "name": "Jane.Doe iPhone",
                "platform": "IOS",
                "version": "10.2.1"
            }
        },
        "policy": {
            "allowRememberDevice": False,
            "rememberDeviceLifetimeInMinutes": 0,
            "rememberDeviceByDefault": False
        },
        "target": {
            "type": "APP",
            "name": "gimmecredstest",
            "label": "Gimme-Creds-Test",
            "_links": {
                "logo": {
                    "name": "medium",
                    "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                    "type": "image/png"
                }
            }
        }
    },
    "_links": {
        "next": {
            "name": "poll",
            "href": "https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify",
            "hints": {
                "allow": [
                    "POST"
                ]
            }
        },
        "cancel": {
            "href": "https://example.okta.com/api/v1/authn/cancel",
            "hints": {
                "allow": [
                    "POST"
                ]
            }
        },
        "prev": {
            "href": "https://example.okta.com/api/v1/authn/previous",
            "hints": {
                "allow": [
                    "POST"
                ]
            }
        },
        "resend": [
            {
                "name": "push",
                "href": "https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify/resend",
                "hints": {
                    "allow": [
                        "POST"
                    ]
                }
            }
        ]
    }
}

        responses.add(responses.POST, 'https://example.okta.com/api/v1/authn/factors/opf9ei43pbAgb2qgc0h7/verify', status=200, body=json.dumps(verify_response))
        result = self.client._login_send_push(self.state_token, self.push_factor)
        assert_equals(result, {'stateToken': self.state_token, 'apiResponse': verify_response})

    @responses.activate
    @patch('builtins.input', return_value='ann@example.com')
    @patch('getpass.getpass', return_value='1234qwert')
    @patch('gimme_aws_creds.webauthn.WebAuthnClient.make_credential', return_value=(b'', AttestationObject.create(
        PackedAttestation.FORMAT, AuthenticatorData.create(
            hashlib.sha256(b'example.okta.com').digest(),
            AuthenticatorData.FLAG.USER_PRESENT | AuthenticatorData.FLAG.USER_VERIFIED | AuthenticatorData.FLAG.ATTESTED,
            0, AttestedCredentialData.create(b'pasten-aag-uuid\0', b'pasten-credential-id', {3: -7})
        ), {'alg': -7, 'sig': b'pasten-sig'}
    )))
    def test_authenticator_enrollment(self, mock_input, mock_password, mock_webauthn_client):
        """ Tests a new webauthn authenticator enrollment """

        setup_factors_response = """
<!DOCTYPE html><html lang="en"><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<div id="subcontainer" class="sign-in-common sign-in">
    <div id="password-verification-challenge" class="sign-in-content rounded-6">
        <h1>Please verify your password</h1>
        <div id="creds.edit" class="ajax-form-editor mfa-challenge-form margin-top-0"><form id="creds.edit.form" class="v-form large-text-inputs clearfix leave-open-on-success" action="/user/verify_password" method="post"><div style="display:none;" class="infobox infobox-error verify-error" id="creds.edit.errors">
                    <span class="icon error-16"></span>
                    <p>Please review the form to correct the following errors:</p>
                    <ul class="bullets">
                        <li><span id="creds.password.error"></span></li>
                    </ul>
                </div>
                <input type="hidden" class="hide" name="_xsrfToken" id="_xsrfToken" value="f94a83d1c56414a0395d340605dd4f16214ed36faa318200ae9826ef98bef4ad"/><label id="creds.password.label" for="creds.password" class="first l-txt normal margin-btm clearfix icon-16" cssErrorClass="error">Password<input id="creds.password" name="password" class="margin-top-10 challenge" tabindex="0" type="password" value="" autocomplete="off"/></label><div class="clearfix clear">
                    <input value="Verify" name="m-save" type="button" id="creds.button.submit" class="ajax-form-submit save button allow-in-read-only allow-in-safe-mode float-l ie7-offset" tabindex="3" onclick="trackEvent('MFA Challenge')"/></div>
            </form></div></div>
</div>
</body>
</html>
"""

        second_factor_response = '''
<!DOCTYPE html>
<head>
<title>Example, Inc - Extra Verification</title>
</head>
<body class="auth okta-container">
<script type="text/javascript">function runLoginPage (fn) {var mainScript = document.createElement('script');mainScript.src = 'https://ok11static.oktacdn.com/assets/js/mvc/loginpage/initLoginPage.pack.88827f9bbcc5016901b032b2e26c64bf.js';mainScript.crossOrigin = 'anonymous';mainScript.integrity = 'sha384-vHr77eH+hWDyAa9aLN7uXxy3ek1uj1quPqidwdV8ljP3b4vpyZQZUtTOSmGQQOLR';document.getElementsByTagName('head')[0].appendChild(mainScript);fn && mainScript.addEventListener('load', function () { setTimeout(fn, 1) });}</script><script type="text/javascript">
(function(){
  var stateToken = '00Xg1Ci6KEli1338pWmP2gHUuYe0c_F4Nwd3fmoK9';
  var authScheme = 'OAUTH2';
  var webauthn = true;
</body>
</html>
'''

        auth_response = {
            "stateToken": "00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
            "type": "SESSION_STEP_UP",
            "expiresAt": "2017-06-15T15:42:31.000Z",
            "status": "SUCCESS",
            "_embedded": {
                "user": {
                    "id": "00u8cakq7vQwtK7sR0h7",
                    "profile": {
                        "login": "ann@example.com",
                        "firstName": "Ann",
                        "lastName": "Pasten",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "target": {
                    "type": "APP",
                    "name": "gimmecredsserver",
                    "label": "Gimme-Creds-Server (Dev)",
                    "_links": {
                        "logo": {
                            "name": "medium",
                            "href": "https://op1static.oktacdn.com/bc/globalFileStoreRecord?id=gfsatgifysE8NG37F0h7",
                            "type": "image/png"
                        }
                    }
                }
            },
            "_links": {
                "next": {
                    "name": "original",
                    "href": "https://example.okta.com/login/step-up/redirect?stateToken=00Wf8xZJ79mSoTYnJqXbvRegT8QB1EX1IBVk1TU7KI",
                    "hints": {
                        "allow": [
                            "GET"
                        ]
                    }
                }
            }
        }

        setup_factor_response = '''
<!DOCTYPE html>
<head>
<title>Example, Inc - Extra Verification</title>
</head>
<body class="auth okta-container">
<script type="text/javascript">function runLoginPage (fn) {var mainScript = document.createElement('script');mainScript.src = 'https://ok11static.oktacdn.com/assets/js/mvc/loginpage/initLoginPage.pack.88827f9bbcc5016901b032b2e26c64bf.js';mainScript.crossOrigin = 'anonymous';mainScript.integrity = 'sha384-vHr77eH+hWDyAa9aLN7uXxy3ek1uj1quPqidwdV8ljP3b4vpyZQZUtTOSmGQQOLR';document.getElementsByTagName('head')[0].appendChild(mainScript);fn && mainScript.addEventListener('load', function () { setTimeout(fn, 1) });}</script><script type="text/javascript">
(function(){
  var stateToken = '13371Ci6KEli4Kopasten2gHUuYe0c_F4Nwd3fmoK9';
  var authScheme = 'OAUTH2';
  var webauthn = true;
</body>
</html>
'''

        introspect_response = {
            "status": "MFA_ENROLL",
            "_embedded": {
                "user": {
                    "id": "13373h4rlzEuUlUOY4x6",
                    "passwordChanged": "2020-04-01T06:01:15.000Z",
                    "profile": {
                        "login": "ann@example.com",
                        "firstName": "Ann",
                        "lastName": "Pasten",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "factors": [
                    {
                        "factorType": "webauthn",
                        "provider": "FIDO",
                        "vendorName": "FIDO",
                        "_links": {
                            "enroll": {
                                "href": "https://example.okta.com/api/v1/authn/factors",
                                "hints": {
                                    "allow": [
                                        "POST"
                                    ]
                                }
                            }
                        },
                        "status": "NOT_SETUP",
                        "enrollment": "OPTIONAL",
                    }
                ]
            },
        }

        enrollment_response = {
            "stateToken": "13371Ci6KEli4Kopasten2gHUuYe0c_F4Nwd3fmoK9",
            "status": "MFA_ENROLL_ACTIVATE",
            "_embedded": {
                "user": {
                    "id": "13373h4rlzEuUlUOY4x6",
                    "profile": {
                        "login": "ann@example.com",
                        "firstName": "Ann",
                        "lastName": "Pasten",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                },
                "factor": {
                    "id": "1337831cjAy4WtMOL4x6",
                    "factorType": "webauthn",
                    "provider": "FIDO",
                    "vendorName": "FIDO",
                    "_embedded": {
                        "activation": {
                            "rp": {
                                "name": "Example, Inc"
                            },
                            "user": {
                                "displayName": "Ann Pasten",
                                "name": "ann@example.com",
                                "id": "13373h4rlzEuUlUOY4x6"
                            },
                            "pubKeyCredParams": [
                                {
                                    "type": "public-key",
                                    "alg": -7
                                },
                                {
                                    "type": "public-key",
                                    "alg": -257
                                }
                            ],
                            "challenge": "QPABsCE0Xkbzlpqb6KbS",
                            "attestation": "direct",
                            "authenticatorSelection": {
                                "userVerification": "optional",
                                "requireResidentKey": False
                            },
                            "u2fParams": {
                                "appid": "https://example.okta.com"
                            },
                            "excludeCredentials": []
                        }
                    }
                }
            },
            "_links": {
                "next": {
                    "name": "activate",
                    "href": "https://example.okta.com/api/v1/authn/factors/1337831cjAy4WtMOL4x6/lifecycle/activate",
                    "hints": {
                        "allow": [
                            "POST"
                        ]
                    }
                },
            }
        }

        mfa_activation_response = {
            "status": "SUCCESS",
            "sessionToken": "13381WI0WOge2jey1crR6AnAkqfXZNUjoAgnWoGXU3WVaHN8dP7Pgln",
            "_embedded": {
                "user": {
                    "id": "13373h4rlzEuUlUOY4x6",
                    "profile": {
                        "login": "ann@example.com",
                        "firstName": "Ann",
                        "lastName": "Pasten",
                        "locale": "en",
                        "timeZone": "America/Los_Angeles"
                    }
                }
            }
        }

        setup_fido_webauthn_url = self.okta_org_url + '/user/settings/factors/setup?factorType=FIDO_WEBAUTHN'
        verify_password_redirect_url = self.okta_org_url + '/user/verify_password?fromURI=%2Fenduser%2Fsettings'

        # Request FIDO authenticator setup - get redirected to password verification
        responses.add(responses.GET, setup_fido_webauthn_url, status=302,
                      adding_headers={'Location': verify_password_redirect_url})
        responses.add(responses.GET, verify_password_redirect_url, status=200, body=setup_factors_response)
        responses.add(responses.POST, self.okta_org_url + '/user/verify_password', status=200)

        # MFA for password verification
        responses.add(responses.GET, self.okta_org_url + '/login/second-factor?fromURI=%2Fenduser%2Fsettings&'
                                                         'forcePrompt=true&hideBgImage=true',
                      status=200, body=second_factor_response)
        responses.add(responses.POST, self.okta_org_url + '/api/v1/authn', status=200, body=json.dumps(auth_response))

        # Continue FIDO authenticator setup once password re-verified
        responses.add(responses.GET, setup_fido_webauthn_url, status=200, body=setup_factor_response)

        # Introspect webauthn factors
        responses.add(responses.POST, self.okta_org_url + '/api/v1/authn/introspect', status=200,
                      body=json.dumps(introspect_response))

        # Enroll & Activate new webauthn factor
        responses.add(responses.POST, introspect_response['_embedded']['factors'][0]['_links']['enroll']['href'],
                      status=200, body=json.dumps(enrollment_response))
        responses.add(responses.POST, enrollment_response['_links']['next']['href'], status=200,
                      body=json.dumps(mfa_activation_response))

        # Finalize factor activation
        enrollment_finalization_redirect_url = self.okta_org_url + '/enduser/settings?enrolledFactor=FIDO_WEBAUTHN'
        enrollment_finalization_url = self.okta_org_url + '/login/sessionCookieRedirect?' \
                                                          'checkAccountSetupComplete=true&token={session_token}&' \
                                                          'redirectUrl={redirect_url}'.format(
            session_token=mfa_activation_response['sessionToken'],
            redirect_url=quote(enrollment_finalization_redirect_url))

        responses.add(responses.GET, url=enrollment_finalization_url, status=302,
                      adding_headers={'Location': enrollment_finalization_redirect_url})
        responses.add(responses.GET, url=enrollment_finalization_redirect_url, status=200)

        credential_id, user_name = self.client.setup_fido_authenticator()
        assert credential_id == b'pasten-credential-id'
        assert user_name == 'ann@example.com'

    @responses.activate
    def test_get_saml_response(self):
        """Test that the SAML reponse was successful"""
        responses.add(responses.GET, 'https://example.okta.com/app/gimmecreds/exkatg7u9g6LJfFrZ0h7/sso/saml', status=200, body=self.login_saml)
        result = self.client.get_saml_response('https://example.okta.com/app/gimmecreds/exkatg7u9g6LJfFrZ0h7/sso/saml')
        assert_equals(result['TargetUrl'], 'https://localhost:8443/saml/SSO')

    @responses.activate
    def test_missing_saml_response(self):
        """Test that the SAML reponse was successful (failed)"""
        responses.add(responses.GET, 'https://example.okta.com/app/gimmecreds/exkatg7u9g6LJfFrZ0h7/sso/saml', status=200, body="")
        with self.assertRaises(RuntimeError):
            result = self.client.get_saml_response('https://example.okta.com/app/gimmecreds/exkatg7u9g6LJfFrZ0h7/sso/saml')

    # @responses.activate
    # def test_get_aws_account_info(self):
    #     """Test the gimme_creds_server response"""
    #     responses.add(responses.POST, 'https://localhost:8443/saml/SSO', status=200)
    #     responses.add(responses.GET, self.gimme_creds_server + '/api/v1/accounts', status=200, body=json.dumps(self.api_results))
    #     # The SAMLResponse value doesn't matter because the API response is mocked
    #     saml_data = {'SAMLResponse': 'BASE64_String', 'RelayState': '', 'TargetUrl': 'https://localhost:8443/saml/SSO'}
    #     result = self.client._get_aws_account_info(self.gimme_creds_server, saml_data)
    #     assert_equals(self.client.aws_access, self.api_results)

    @patch('builtins.input', return_value='0')
    def test_choose_factor_sms(self, mock_input):
        """ Test selecting SMS as a MFA"""
        result = self.client._choose_factor(self.factor_list)
        assert_equals(result, self.sms_factor)

    @patch('builtins.input', return_value='1')
    def test_choose_factor_push(self, mock_input):
        """ Test selecting Okta Verify as a MFA"""
        result = self.client._choose_factor(self.factor_list)
        assert_equals(result, self.push_factor)

    @patch('builtins.input', return_value='2')
    def test_choose_factor_totp(self, mock_input):
        """ Test selecting TOTP code as a MFA"""
        result = self.client._choose_factor(self.factor_list)
        assert_equals(result, self.totp_factor)

    @patch('builtins.input', return_value='12')
    def test_choose_bad_factor_totp(self, mock_input):
        """ Test selecting an invalid MFA factor"""
        with self.assertRaises(errors.GimmeAWSCredsExitBase):
            result = self.client._choose_factor(self.factor_list)

    @patch('builtins.input', return_value='3')
    def test_choose_factor_webauthn(self, mock_input):
        """ Test selecting webauthn code as a MFA"""
        result = self.client._choose_factor(self.factor_list)
        assert_equals(result, self.webauthn_factor)

    @patch('builtins.input', return_value='a')
    def test_choose_non_number_factor_totp(self, mock_input):
        """ Test entering a non number value as MFA factor"""
        with self.assertRaises(errors.GimmeAWSCredsExitBase):
            result = self.client._choose_factor(self.factor_list)

    def test_build_factor_name_sms(self):
        """ Test building a display name for SMS"""
        result = self.client._build_factor_name(self.sms_factor)
        assert_equals(result, "sms: +1 XXX-XXX-1234")

    def test_build_factor_name_push(self):
        """ Test building a display name for push"""
        result = self.client._build_factor_name(self.push_factor)
        assert_equals(result, "Okta Verify App: SmartPhone_IPhone: Jane.Doe iPhone")

    def test_build_factor_name_totp(self):
        """ Test building a display name for TOTP"""
        result = self.client._build_factor_name(self.totp_factor)
        assert_equals(result, "token:software:totp( OKTA ) : jane.doe@example.com")

    def test_build_factor_name_hardware(self):
        """ Test building a display name for hardware"""
        result = self.client._build_factor_name(self.hardware_factor)
        assert_equals(result, "token:hardware: YUBICO")

    def test_build_factor_name_unknown(self):
        """ Handle an unknown MFA factor"""
        with self.captured_output() as (out, err):
            result = self.client._build_factor_name(self.unknown_factor)
            assert_equals(result, "Unknown MFA type: UNKNOWN_FACTOR")

    def test_build_factor_name_webauthn_unregistered(self):
        """ Test building a display name for an unregistered webauthn factor """
        result = self.client._build_factor_name(self.webauthn_factor)
        assert_equals(result, "webauthn: webauthn")

    def test_build_factor_name_webauthn_unregistered_with_authenticator_name(self):
        """ Test building a display name for an unregistered webauthn factor with a specified authenticator name """
        webauthn_factor_with_authenticator_name = self.webauthn_factor.copy()

        authenticator_name = 'Pasten Authenticator'
        webauthn_factor_with_authenticator_name['profile']['authenticatorName'] = authenticator_name

        result = self.client._build_factor_name(self.webauthn_factor)
        assert_equals(result, "webauthn: " + authenticator_name)

    @patch('gimme_aws_creds.registered_authenticators.RegisteredAuthenticators.get_authenticator_user',
           return_value='jane.doe@example.com')
    def test_build_factor_name_webauthn_registered(self, mock_input):
        """ Test building a display name for a registered webauthn factor """
        result = self.client._build_factor_name(self.webauthn_factor)
        assert_equals(result, "webauthn: jane.doe@example.com")

    # def test_get_app_by_name(self):
    #     """ Test selecting app by name"""
    #     self.client.aws_access = self.api_results
    #     result = self.client.get_app_by_name('Sample AWS Account')
    #     assert_equals(result['name'], 'Sample AWS Account')
    #
    # def test_get_role_by_name(self):
    #     """ Test selecting app by name"""
    #     self.client.aws_access = self.api_results
    #     result = self.client.get_role_by_name(self.api_results[0], 'ReadOnly')
    #     assert_equals(result['name'], 'ReadOnly')

    # @patch('builtins.input', return_value='0')
    # def test_choose_role(self, mock_input):
    #     """ Test selecting role with user input"""
    #     result = self.client.choose_role(self.api_results[0])
    #     assert_equals(result['name'], 'ReadOnly')
    #
    # @patch('builtins.input', return_value='0')
    # def test_choose_app(self, mock_input):
    #     """ Test selecting app with user input"""
    #     self.client.aws_access = self.api_results
    #     result = self.client.choose_app()
    #     assert_equals(result['name'], 'Sample AWS Account')
