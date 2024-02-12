import time

import html5lib
from furl import furl

from . import version


class DuoMfaDenied(BaseException):
    """ Duo MFA was denied """

    def __init__(self, response):
        super(DuoMfaDenied, self).__init__(f'Duo MFA denied: {response}')


class OktaDuoUniversal:
    """ Handles interaction with the Duo Universal Prompt """

    def __init__(self, ui, session, state_token, okta_factor, remember_device, duo_factor='Duo Push', duo_passcode=None):
        self.ui = ui
        self.state_token = state_token
        self.okta_factor = okta_factor
        self.remember_device = remember_device
        self.session = session
        if duo_factor not in ['Duo Push', 'Passcode', 'Phone Call']:
            raise Exception('Preferred Duo Universal factor must be one of: Duo Push, Passcode, Phone Call')
        self.duo_factor = duo_factor
        self.duo_passcode = duo_passcode

    def do_auth(self):
        """ Follow Duo Universal Prompt flow through to an active Okta user session """

        duo_prompt_url, okta_profile_login = self._initiate_okta_factor_verification()
        duo_origin, duo_plugin_form_response = self._handle_duo_plugin_form(duo_prompt_url)

        # Submit second Duo form (login-form), which triggers a Duo Push, phone call, or accepts the Passcode
        login_form_action, duo_login_form_data = self._get_duo_universal_login_form_data(duo_plugin_form_response)
        login_form_action_url = furl(duo_origin) / login_form_action
        duo_factor, duo_sid, duo_txid, duo_xsrf = self._submit_duo_login_form(duo_login_form_data,
                                                                              login_form_action_url)

        self.ui.info(f"Duo Universal: Using {self.duo_factor}...")

        self._wait_for_duo_universal_transaction(duo_origin, duo_txid, duo_sid)

        # Once Duo has been approved, load the OIDC exit URL to be redirected to Okta and gain a user session
        oidc_exit_url = furl(duo_origin) / 'frame/v4/oidc/exit'
        exit_headers = self._get_form_headers()
        exit_response = self.session.post(
            oidc_exit_url.url,
            data={
                'txid': duo_txid,
                'sid': duo_sid,
                'factor': duo_factor,
                '_xsrf': duo_xsrf,
                'device_key': '',
                'dampen_choice': 'false',
            },
            headers=exit_headers,
        )
        exit_response.raise_for_status()

        # The claims_provider factor immediately yields an active user session, no subsequent request for SID required.
        return {
            'apiResponse': {
                'status': 'SUCCESS',
                'userSession': {
                    "username": okta_profile_login,
                    "session": self.session.cookies['sid'],
                    "device_token": self.session.cookies['DT']
                },
                'sessionToken': self.session.cookies['sid']
            },
        }

    def _submit_duo_login_form(self, duo_login_form_data, login_form_action_url):
        # Submit Duo's form id=login-form, which triggers a Duo Push, phone call, or accepts a Passcode.
        duo_login_form_response = self.session.post(
            login_form_action_url.url,
            data=duo_login_form_data,
            headers=self._get_form_headers(),
        )
        duo_login_form_response.raise_for_status()
        duo_sid = duo_login_form_data['sid']
        duo_factor = duo_login_form_data['factor']
        duo_xsrf = duo_login_form_data['_xsrf']
        duo_login_response_data = duo_login_form_response.json()
        if duo_login_response_data['stat'] != 'OK':
            raise Exception(f"Triggering Duo MFA failed: {duo_login_form_response.content}")
        duo_txid = duo_login_response_data['response']['txid']
        return duo_factor, duo_sid, duo_txid, duo_xsrf

    def _handle_duo_plugin_form(self, duo_prompt_url):
        # Request Duo prompt
        verify_get_response = self.session.get(
            duo_prompt_url,
        )
        verify_get_response.raise_for_status()
        duo_origin = furl(verify_get_response.url).origin
        # Submit first Duo form (plugin_form)
        form_data = self._get_duo_universal_plugin_form_data(verify_get_response)
        duo_plugin_form_response = self.session.post(
            verify_get_response.url,
            data=form_data,
            headers=self._get_form_headers(),
        )
        duo_plugin_form_response.raise_for_status()
        return duo_origin, duo_plugin_form_response

    def _initiate_okta_factor_verification(self):
        # POST to the Okta factor verify URL gives us the URL to request to load Duo
        verify_post_response = self.session.post(
            self.okta_factor['_links']['verify']['href'],
            params={'rememberDevice': self.remember_device},
            json={'stateToken': self.state_token},
        )
        verify_post_response.raise_for_status()
        verify_response_data = verify_post_response.json()
        duo_prompt_url = verify_response_data['_links']['next']['href']
        okta_profile_login = verify_response_data['_embedded']['user']['profile']['login']
        return duo_prompt_url, okta_profile_login

    def _wait_for_duo_universal_transaction(self, duo_host, txid, sid):
        status_url = furl(duo_host) / 'frame/v4/status'
        status_data = {
            'txid': txid,
            'sid': sid
        }
        headers = self._get_form_headers()

        tries = 0
        while tries < 16:
            tries += 1
            time.sleep(0.5)

            status_response = self.session.post(
                status_url.url,
                data=status_data,
                headers=headers,
            )
            status_response.raise_for_status()

            json_response = status_response.json()
            if json_response['stat'] != 'OK':
                raise Exception(f"Error checking Duo MFA status: {status_response.text}")

            if json_response['response']['status_code'] == 'allow':
                return txid
            if json_response['response']['status_code'] == 'deny':
                raise DuoMfaDenied(json_response)

        raise Exception('Timed out waiting for Duo MFA')

    @staticmethod
    def _get_form_headers():
        form_headers = {
            'User-Agent': "gimme-aws-creds {}".format(version),
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        return form_headers

    def _get_duo_universal_login_form_data(self, plugin_form_response):
        """ Get form data to post when submitting the Duo login-form """

        doc = html5lib.parse(plugin_form_response.content, namespaceHTMLElements=False)
        form_action = doc.find('.//form[@id="login-form"]').get('action')
        form_data = {}
        for field in doc.iterfind('.//form[@id="login-form"]/input'):
            form_data[field.get('name')] = field.get('value')

        preferred_device = self._find_device_to_use(doc)

        form_data['factor'] = self.duo_factor
        form_data['device'] = preferred_device
        form_data['postAuthDestination'] = 'OIDC_EXIT'
        if self.duo_passcode:
            form_data['passcode'] = self.duo_passcode

        return form_action, form_data

    @staticmethod
    def _find_device_to_use(doc):
        device = doc.find('.//input[@name="preferred_device"]').get('value')
        if device is None or device == '':
            device = doc.find('.//select[@name="device"]/option').get('value')
        return device

    @staticmethod
    def _get_duo_universal_plugin_form_data(response):
        """ Get form data to post when submitting the Duo plugin_form """

        doc = html5lib.parse(response.content, namespaceHTMLElements=False)
        form_data = {}
        for field in doc.iterfind('.//form[@id="plugin_form"]/input'):
            form_data[field.get('name')] = field.get('value')

        return form_data
