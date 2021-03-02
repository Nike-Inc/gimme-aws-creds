# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Copyright 2018 Nathan V
# https://github.com/nathan-v/aws_okta_keyman
"""All the Duo things."""

import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process

import requests


class PasscodeRequired(BaseException):
    """A 2FA Passcode Must Be Entered"""

    def __init__(self, factor, state_token):
        self.factor = factor
        self.state_token = state_token
        super(PasscodeRequired, self).__init__()


class FactorRequired(BaseException):
    """A 2FA Factor Must Be Entered"""

    def __init__(self, factor, state_token):
        self.factor = factor
        self.state_token = state_token
        super(FactorRequired, self).__init__()


class QuietHandler(BaseHTTPRequestHandler, object):
    """We have to do this HTTP sever silliness because the Duo widget has to be
    presented over HTTP or HTTPS or the callback won't work.
    """

    def __init__(self, html, *args):
        self.html = html
        super(QuietHandler, self).__init__(*args)

    def log_message(self, _format, *args):
        """Mute the server log."""

    def do_GET(self):
        """Handle the GET and displays the Duo iframe."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(self.html.encode('utf-8'))


class Duo:
    """Does all the background work needed to serve the Duo iframe."""

    def __init__(self, gac_ui, details, state_token, socket, factor=None,):
        self.ui = gac_ui
        self.socket = socket
        self.details = details
        self.token = state_token
        self.factor = factor
        self.html = None
        self.session = requests.Session()

    def trigger_web_duo(self):
        """Start the webserver with the data needed to display the Duo
        iframe for the user to see.
        """
        host = self.details['host']
        sig = self.details['signature']
        script = self.details['_links']['script']['href']
        callback = self.details['_links']['complete']['href']

        self.html = '''<p style="text-align:center">You may close this
         after the next page loads successfully</p>
        <iframe id="duo_iframe" style="margin: 0 auto;display:block;"
        width="620" height="330" frameborder="0"></iframe>
        <form method="POST" id="duo_form" action="{cb}">
        <input type="hidden" name="stateToken" value="{tkn}" /></form>
        <script src="{scr}"></script><script>Duo.init(
          {{'host': '{hst}','sig_request': '{sig}','post_action': '{cb}'}}
        );</script>'''.format(tkn=self.token, scr=script,
                              hst=host, sig=sig,
                              cb=callback)
        proc = Process(target=self.duo_webserver)
        proc.start()
        time.sleep(10)
        proc.terminate()

    def duo_webserver(self):
        """HTTP webserver."""
        httpd = HTTPServer(self.socket, self.handler_with_html)
        httpd.serve_forever()

    def handler_with_html(self, *args):
        """Call the handler and include the HTML."""
        return QuietHandler(self.html, *args)

    def trigger_duo(self, passcode=""):
        """Try to get a Duo Push without needing an iframe

        Args:
            passcode: String passcode to pass along to the OTP factor
        """
        sid = self.do_auth(None, None)
        if self.factor == "call":
            transaction_id = self.get_txid(sid, "Phone+Call")
        elif self.factor == "passcode":
            if passcode:
                transaction_id = self.get_txid(sid, "Passcode", passcode)
            else:
                raise Exception("Cannot use passcode without one provided")
        elif self.factor == "push":
            transaction_id = self.get_txid(sid, "Duo+Push")
        else:
            raise Exception("Requested Duo factor not supported")
        auth = self.get_status(transaction_id, sid)
        return auth

    def do_auth(self, sid, certs_url):
        """Handle initial auth with Duo

        Args:
            sid: String Duo session ID if we have it
            certs_url: String certificates URL if we have it

        Returns:
            String Duo session ID
        """
        txid = self.details['signature'].split(":")[0]
        fake_path = 'http://0.0.0.0:3000/duo&v=2.1'
        url = "https://{}/frame/web/v1/auth?tx={}&parent={}".format(
            self.details['host'], txid, fake_path)

        if sid and certs_url:
            self.session.params = {sid: sid, certs_url: certs_url}

        self.session.headers = {
            'Origin': "https://{}".format(self.details['host']),
            'Content-Type': "application/x-www-form-urlencoded"
        }

        ret = self.session.post(url, allow_redirects=False)

        if ret.status_code == 302:
            try:
                location = ret.headers['Location']
                sid = location.split("=")[1]
            except KeyError:
                raise Exception("Location missing from auth response header.")
        elif ret.status_code == 200 and sid is None:
            sid = ret.json()['response']['sid']
            certs_url = ret.json()['response']['certs_url']
            sid = self.do_auth(sid, certs_url)
        else:
            raise Exception("Duo request failed.")

        return sid

    def get_txid(self, sid, factor, passcode=None):
        """Get Duo transaction ID

        Args:
            sid: String Duo session ID
            factor: String to tell Duo which factor to use
            passcode: OTP passcode string

        Returns:
            String Duo transaction ID
        """
        url = "https://{}/frame/prompt".format(self.details['host'])
        self.session.headers = {
            'Origin': "https://{}".format(self.details['host']),
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Requested-With': 'XMLHttpRequest'
        }

        params = (
            "sid={}&device=phone1&"
            "factor={}&out_of_date=False").format(sid, factor)

        if passcode:
            params = "{}&passcode={}".format(params, passcode)

        url = "{}?{}".format(url, params)

        ret = self.session.post(url)
        return ret.json()['response']['txid']

    def get_status(self, transaction_id, sid):
        """Get Duo auth status

        Args:
            transaction_id: String Duo transaction ID
            sid: String Duo session ID

        Returns:
            String authorization from Duo to use in the Okta callback
        """
        url = "https://{}/frame/status".format(self.details['host'])
        self.session.headers = {
            'Origin': "https://{}".format(self.details['host']),
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Requested-With': 'XMLHttpRequest'
        }

        params = "sid={}&txid={}".format(sid, transaction_id)

        url = "{}?{}".format(url, params)

        tries = 0
        auth = None
        while auth is None and tries < 30:
            tries += 1
            ret = self.session.post(url)

            if ret.status_code != 200:
                raise Exception("Push request failed with status {}".format(
                    ret.status_code))

            result = ret.json()
            self.ui.info("status: {}".format(result['response']['status']))
            if result['response'].get('result') == 'FAILURE':
                raise Exception('DUO MFA failed: {}'.format(format(result['response']['status'])))
            if result['stat'] == "OK":
                if 'cookie' in result['response']:
                    auth = result['response']['cookie']
                elif 'result_url' in result['response']:
                    auth = self.do_redirect(
                        result['response']['result_url'], sid)
            else:
                time.sleep(1)

        if auth is None:
            raise Exception('Did not get callback information from Duo')
        return auth

    def do_redirect(self, url, sid):
        """Deal with redirected response from Duo

        Args:
            url: String URL we need to follow to try and get the auth
            sid: String duo session ID

        Returns:
            String Duo authorization to use in the Okta callback
        """
        url = "https://{}{}?sid={}".format(self.details['host'], url, sid)
        self.session.headers = {
            'Origin': "https://{}".format(self.details['host']),
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Requested-With': 'XMLHttpRequest'
        }

        ret = self.session.post(url)

        if ret.status_code != 200:
            raise Exception("Bad status from Duo after redirect {}".format(
                ret.status_code))

        result = ret.json()

        if 'cookie' in result['response']:
            return result['response']['cookie']
