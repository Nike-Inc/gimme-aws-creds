import json
import requests
import sys
from pprint import pprint


class CerberusMiniClient(object):
    """THis is a Cerberus Mini Client Class that does Cerberus stuff"""
    HEADERS = {"Content-Type": "application/json"}

    def __init__(self, username, password):
        self.cerberus_url = 'https://prod.cerberus.nikecloud.com/'
        self.username = username
        self.password = password
        self.token = None
        self.set_token()

    def set_token(self):
        """sets client token from Cerberus"""
        auth_resp = self.get_auth()
        if auth_resp['status'] == 'mfa_req':
            token_resp = self.get_mfa(auth_resp)
        else:
            token_resp = auth_resp
        token = token_resp['data']['client_token']['client_token']
        self.token = token

    def get_token(self):
        """Returns a client token from Cerberus"""
        return self.token

    def get_auth(self):
        """Returns auth respose which has client token unless MFA is required"""
        auth_resp = requests.get(self.cerberus_url + '/v2/auth/user', auth=(self.username, self.password))
        if auth_resp.status_code != 200:
           print("ERROR: " + auth_resp.json()['errors'][0]['message'])
           sys.exit(2)
        auth_resp_json = json.loads(auth_resp.text)
        return auth_resp_json

    def get_mfa(self, auth_resp):
        """Gets MFA code from user and returns response which includes the client token"""
        # TODO check if there is more than 1 device.
        # currently cerberus only support Google Authenicator
        sec_code = input('Enter ' + auth_resp['data']['devices'][0]['name'] + ' security code: ')
        mfa_resp = requests.post(self.cerberus_url + '/v2/auth/mfa_check',
                                json={'otp_token': sec_code,
                                      'device_id': auth_resp['data']['devices'][0]['id'],
                                      'state_token': auth_resp['data']['state_token']},
                                       headers=self.HEADERS)
        if mfa_resp.status_code != 200:
            print("ERROR: " + auth_resp['errors'][0]['message'])
            sys.exit(2)
        mfa_resp_json = json.loads(mfa_resp.text)
        return mfa_resp_json

    def get_sdb_path(self,sdb):
        """Returns the path for a SDB"""
        id = self.get_sdb_id(sdb)
        sdb_resp = requests.get(self.cerberus_url + '/v1/safe-deposit-box/' + id + '/',
                                headers={'Content-Type' : 'application/json', 'X-Vault-Token': self.token})
        if sdb_resp.status_code != 200:
           print("ERROR: " + sdb_resp.json()['errors'][0]['message'])
           sys.exit(2)
        sdb_resp_json = json.loads(sdb_resp.text)
        path = sdb_resp_json['path']
        return path

    def get_sdb_keys(self,path):
        """Returns the keys for a SDB, which are need for the full vault path"""
        list_resp = requests.get(self.cerberus_url + '/v1/secret/' + path + '/?list=true',
                                headers= {'Content-Type' : 'application/json', 'X-Vault-Token': self.token})
        if list_resp.status_code != 200:
           print("ERROR: " + list_resp.json()['errors'][0]['message'])
           sys.exit(2)
        list_resp_json = json.loads(list_resp.text)
        return list_resp_json['data']['keys']

    def get_sdb_id(self,sdb):
        """ Return the ID for the given safety deposit box"""
        sdb_resp = requests.get(self.cerberus_url + '/v1/safe-deposit-box',
                                headers= {'Content-Type' : 'application/json', 'X-Vault-Token': self.token})
        if sdb_resp.status_code != 200:
           print("ERROR: " + sdb_resp.json()['errors'][0]['message'])
           sys.exit(2)
        sdb_resp_json = json.loads(sdb_resp.text)
        for r in sdb_resp_json:
            if r['name'] == sdb:
                return str(r['id'])
        print("ERROR: " + sdb + " not found")
        sys.exit(2)

    def get_secret(self,vault_path,key):
        secret_resp = requests.get(cerberus_url + '/v1/secret/' + vault_path,
                                  headers={'Content-Type' : 'application/json', 'X-Vault-Token': token})
        if secret_resp.status_code != 200:
            print("ERROR: " + secret_resp.json()['errors'][0]['message'])
            sys.exit(2)
        secret_resp_json = json.loads(secret_resp.text)
        if key in secret_resp_json['data']:
            return secret_resp_json['data'][key])
        else:
            print("ERROR: key " + key + " not found")
            sys.exit(2)
