import json
import unittest
from unittest.mock import Mock

import requests
import responses
from tests import read_fixture

from gimme_aws_creds.duo_universal import OktaDuoUniversal
from tests.user_interface_mock import MockUserInterface


class TestDuoUniversalClient(unittest.TestCase):
    def setUp(self):
        self.OKTA_STATE_TOKEN = 'statetokenstatetokenstatetokenstatetokenstateto'
        self.OKTA_LOGIN = 'okta.user@example.com'
        self.OKTA_FIRST_NAME = 'Okta'
        self.OKTA_LAST_NAME = 'User'
        self.OKTA_FACTOR_ID = 'oktafactorid'
        self.OKTA_FACTOR = {
            'factorType': 'claims_provider',
            'provider': 'CUSTOM',
            'vendorName': 'Duo Universal Prompt',
            '_links': {
                'verify': {
                    'href': 'https://oktatenant.oktapreview.com/sso/idps/foo/verify',
                    'hints': {
                        'allow': ['POST']
                    }
                }
            }
        }
        self.OKTA_DT_VALUE = 'oktadtvalue'
        self.OKTA_SID_VALUE = 'oktasidvalue'

        self.REQ_0_OKTA_AUTHN_FACTORS_VERIFY_RESPONSE = {
            'stateToken': self.OKTA_STATE_TOKEN,
            'expiresAt': '2100-10-17T19:35:07.000Z', 'status': 'MFA_CHALLENGE',
            'factorResult': 'CHALLENGE',
            '_embedded': {
                'user': {
                    'id': 'oktauseridoktauserid',
                    'passwordChanged': '2100-05-17T18:56:58.000Z',
                    'profile': {
                        'login': self.OKTA_LOGIN,
                        'firstName': self.OKTA_FIRST_NAME,
                        'lastName': self.OKTA_LAST_NAME,
                        'locale': 'en_US', 'timeZone': 'America/Los_Angeles'
                    }
                },
                'factor': {
                    'id': self.OKTA_FACTOR_ID,
                    'factorType': 'claims_provider',
                    'provider': 'CUSTOM',
                    'vendorName': 'Duo Universal Prompt'},
                'policy': {
                    'allowRememberDevice': True,
                    'rememberDeviceLifetimeInMinutes': 720,
                    'rememberDeviceByDefault': False,
                    'factorsPolicyInfo': {}
                }
            },
            '_links': {
                'next': {
                    'name': 'redirect',
                    'href': f'https://oktatenant.oktapreview.com/sso/idps/oktaclaimsidpid?stateToken={self.OKTA_STATE_TOKEN}',
                    'hints': {
                        'allow': ['GET']
                    }
                },
                'cancel': {
                    'href': 'https://oktatenant.oktapreview.com/api/v1/authn/cancel',
                    'hints': {
                        'allow': ['POST']
                    }
                },
                'prev': {
                    'href': 'https://oktatenant.oktapreview.com/api/v1/authn/previous',
                    'hints': {
                        'allow': ['POST']
                    }
                }
            }
        }
        self.DUO_ORIGIN = 'https://duo-tenant.duosecurity.com'
        self.DUO_TX = 'tttttttttttttttttttttttttttttttttttt.tttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttt.ttttt_tt-tttttttttttttttttttttttt_tttttttttttttttttttttttttt_ttttttttttttttttttt-tt-tt'
        self.DUO_SID = 'frameless-aaaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaaaa'
        self.DUO_AUTHORIZE_URL = f'{self.DUO_ORIGIN}/oauth/v1/authorize?client_id=oktaclientidoktaclientid&response_type=code&scope=openid&request=rrrrrrrrrrrrrrrrrrrr.rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr._rrrrrrrrrrr-rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr'
        self.DUO_FRAMELESS_AUTH_PATH = f'/frame/frameless/v4/auth?sid={self.DUO_SID}&tx={self.DUO_TX}'
        self.DUO_PROMPT_PATH = '/frame/prompt?sid=frameless-aaaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaaaa'
        self.DUO_XSRF = 'xsrfxsrfxsrfxsrfxsrfxsrfxsrfxsrfxsrfxs'
        self.DUO_PLUGIN_FORM_CONTENT = read_fixture('duo_universal_plugin_form.html')
        self.DUO_LOGIN_FORM_CONTENT = read_fixture('duo_universal_login_form.html')
        self.DUO_TXID = 'txidtxid-txid-txid-txid-txidtxid'
        self.DUO_LOGIN_FORM_SUBMISSION_RESPONSE = {
            'stat': 'OK',
            'response': {
                'txid': self.DUO_TXID
            }
        }
        self.DUO_STATUS_PUSH_IN_PROGRESS_RESPONSE = {
            'stat': 'OK',
            'response': {
                'status_enum': 13,
                'status_code': 'pushed'
            }
        }
        self.DUO_STATUS_PUSH_COMPLETE_RESPONSE = {
            'stat': 'OK',
            'response': {
                'status_enum': 5,
                'status_code': 'allow',
                'result': 'SUCCESS',
                'reason': 'User approved',
                'post_auth_action': 'oidc_exit'
            }
        }

    @responses.activate(registry=responses.registries.OrderedRegistry)
    def test_universal_push(self):
        self.configure_duo_responses(duo_factor='Duo Push')

        session = requests.Session()
        duo = OktaDuoUniversal(ui=MockUserInterface(),
                               session=session,
                               state_token=self.OKTA_STATE_TOKEN,
                               okta_factor=self.OKTA_FACTOR,
                               remember_device=True,
                               duo_factor='Duo Push')
        result = duo.do_auth()
        assert result == {
            'apiResponse': {
                'status': 'SUCCESS',
                'userSession': {
                    'username': self.OKTA_LOGIN,
                    'session': self.OKTA_SID_VALUE,
                    'device_token': self.OKTA_DT_VALUE
                }
            },
        }

    @responses.activate(registry=responses.registries.OrderedRegistry)
    def test_universal_phone_call(self):
        self.configure_duo_responses(duo_factor='Phone Call')
        session = requests.Session()
        duo = OktaDuoUniversal(ui=MockUserInterface(),
                               session=session,
                               state_token=self.OKTA_STATE_TOKEN,
                               okta_factor=self.OKTA_FACTOR,
                               remember_device=True,
                               duo_factor='Phone Call')
        result = duo.do_auth()
        assert result == {
            'apiResponse': {
                'status': 'SUCCESS',
                'userSession': {
                    'username': self.OKTA_LOGIN,
                    'session': self.OKTA_SID_VALUE,
                    'device_token': self.OKTA_DT_VALUE
                }
            },
        }

    @responses.activate(registry=responses.registries.OrderedRegistry)
    def test_universal_passcode(self):
        self.configure_duo_responses(duo_factor='Passcode', passcode='12345')
        session = requests.Session()
        duo = OktaDuoUniversal(ui=MockUserInterface(),
                               session=session,
                               state_token=self.OKTA_STATE_TOKEN,
                               okta_factor=self.OKTA_FACTOR,
                               remember_device=True,
                               duo_factor='Passcode',
                               duo_passcode='12345')
        result = duo.do_auth()
        assert result == {
            'apiResponse': {
                'status': 'SUCCESS',
                'userSession': {
                    'username': self.OKTA_LOGIN,
                    'session': self.OKTA_SID_VALUE,
                    'device_token': self.OKTA_DT_VALUE
                }
            },
        }

    def test_no_preferred_device(self):
        session = requests.Session()
        login_form_response = Mock()
        login_form_response.content = read_fixture('duo_universal_login_form_without_preferred_device.html')
        duo = OktaDuoUniversal(ui=MockUserInterface(),
                               session=session,
                               state_token=self.OKTA_STATE_TOKEN,
                               okta_factor=self.OKTA_FACTOR,
                               remember_device=True,
                               duo_factor='Passcode',
                               duo_passcode='12345')
        form_action, form_data = duo._get_duo_universal_login_form_data(login_form_response)
        assert form_data['device'] == 'phone1'

    def configure_duo_responses(self, duo_factor, passcode=None):
        # Initial request to Okta to verify IDP factor
        responses.add(responses.POST,
                      self.OKTA_FACTOR['_links']['verify']['href'] + '?rememberDevice=True',
                      body=json.dumps(self.REQ_0_OKTA_AUTHN_FACTORS_VERIFY_RESPONSE),
                      match=[
                          responses.matchers.json_params_matcher(
                              {
                                  'stateToken': self.OKTA_STATE_TOKEN
                              }
                          )]
                      )
        # Request to Okta IDP next step
        responses.add(method=responses.GET,
                      url=self.REQ_0_OKTA_AUTHN_FACTORS_VERIFY_RESPONSE['_links']['next']['href'],
                      status=302,
                      adding_headers={
                          'Location': self.DUO_AUTHORIZE_URL,
                          'Set-Cookie': f'DT={self.OKTA_DT_VALUE};Version=1;Path=/;Max-Age=63072000;Secure;Expires=Thu, 16 Oct 2100 19:30:07 GMT;HttpOnly'
                      })
        # Duo redirects a couple of times before presenting a form
        responses.add(method=responses.GET,
                      url=self.DUO_AUTHORIZE_URL,
                      status=303,
                      adding_headers={
                          'Location': self.DUO_FRAMELESS_AUTH_PATH
                      })
        responses.add(method=responses.GET,
                      url=self.DUO_ORIGIN + self.DUO_FRAMELESS_AUTH_PATH,
                      body=self.DUO_PLUGIN_FORM_CONTENT
                      )
        # Duo plugin-form submission
        responses.add(method=responses.POST,
                      url=self.DUO_ORIGIN + self.DUO_FRAMELESS_AUTH_PATH,
                      status=302,
                      adding_headers={
                          'Location': self.DUO_PROMPT_PATH
                      },
                      match=[
                          responses.matchers.urlencoded_params_matcher(
                              {
                                  'tx': self.DUO_TX,
                                  '_xsrf': self.DUO_XSRF,
                                  'parent': 'None',
                              }
                          )]
                      )
        # Duo presents a second form, login-form
        responses.add(method=responses.GET,
                      url=self.DUO_ORIGIN + self.DUO_PROMPT_PATH,
                      body=self.DUO_LOGIN_FORM_CONTENT
                      )
        # login-form submit, which triggers Push or Phone call if that's what the user wanted
        duo_login_form_values = {
            # Important to Duo
            'sid': self.DUO_SID,
            'postAuthDestination': 'OIDC_EXIT',
            'factor': duo_factor,
            'device': 'phone1',
            '_xsrf': 'xsrfxsrfxsrfxsrfxsrfxsrfxsrfxsrfxsrfxs',
            # Unimportant for triggering universal MFA, but part of the form inputs
            'should_update_dm': 'False',
            'should_retry_u2f_timeouts': 'True',
            'preferred_factor': 'Duo Push',
            'preferred_device': 'phone1',
            'out_of_date': 'False',
            'itype': 'okta',
            'has_phone_that_requires_compliance_text': 'False',
            'days_to_block': 'None',
            'days_out_of_date': '0',
            'url': '/frame/prompt',
            'ukey': 'duoukeyvalue'
        }
        if passcode:
            duo_login_form_values['passcode'] = passcode
        responses.add(method=responses.POST,
                      url=self.DUO_ORIGIN + '/frame/prompt',
                      body=json.dumps(self.DUO_LOGIN_FORM_SUBMISSION_RESPONSE),
                      match=[responses.matchers.urlencoded_params_matcher(
                          duo_login_form_values)]
                      )
        # 'No response yet' status
        responses.add(method=responses.POST,
                      url=self.DUO_ORIGIN + '/frame/v4/status',
                      body=json.dumps(self.DUO_STATUS_PUSH_IN_PROGRESS_RESPONSE),
                      match=[responses.matchers.urlencoded_params_matcher(
                          {
                              'txid': self.DUO_TXID,
                              'sid': self.DUO_SID,
                          })]
                      )
        # 'User approved' status
        responses.add(method=responses.POST,
                      url=self.DUO_ORIGIN + '/frame/v4/status',
                      body=json.dumps(self.DUO_STATUS_PUSH_COMPLETE_RESPONSE),
                      match=[responses.matchers.urlencoded_params_matcher(
                          {
                              'txid': self.DUO_TXID,
                              'sid': self.DUO_SID,
                          })]
                      )
        # Client posts to a Duo OIDC exit URL, which redirects to Okta
        okta_oidc_callback = 'https://oktatenant.oktapreview.com/oauth2/v1/authorize/callback?state=oidcexitstate&code=oidccode'
        responses.add(method=responses.POST,
                      url=self.DUO_ORIGIN + '/frame/v4/oidc/exit',
                      status=303,
                      adding_headers={
                          'Location': okta_oidc_callback
                      },
                      match=[responses.matchers.urlencoded_params_matcher(
                          {
                              'txid': self.DUO_TXID,
                              'sid': self.DUO_SID,
                              'dampen_choice': 'false',
                              '_xsrf': self.DUO_XSRF,
                              'factor': duo_factor,
                          })]
                      )
        responses.add(method=responses.GET,
                      url=okta_oidc_callback,
                      body='<html></html>',
                      adding_headers={
                          'Set-Cookie': f'sid={self.OKTA_SID_VALUE};Version=1;Path=/;Secure'
                      }
                      )
