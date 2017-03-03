import json
import requests

class OktaClient(object):

    def __init__(self, okta_api_key, idp_entry_url):
        self.okta_api_key = okta_api_key
        self.idp_entry_url = idp_entry_url

    def get_headers(self):
        headers = {'Accept' : 'application/json',
                   'Content-Type' : 'application/json',
                   'Authorization' : 'SSWS ' + self.okta_api_key}
        return headers


    def get_login_response(self, username, password):
        """ gets the login response from Okta and returns the json response"""
        headers = self.get_headers()
        response = requests.post(self.idp_entry_url + '/authn',
                                 json={'username': username, 'password': password},
                                 headers=headers)
        if response.status_code != 200:
            print("ERROR: " + response['errors'][0]['message'])
            sys.exit(2)
        response_json = json.loads(response.text)
        return response_json
