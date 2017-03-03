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

    def get_app_links(self,login_resp):
        """ return appLinks obejct for the user """
        headers = self.get_headers()
        user_id = login_resp['_embedded']['user']['id']
        response = requests.get(self.idp_entry_url + '/users/' + user_id + '/appLinks',
              headers=headers, verify=True)
        app_resp = json.loads(response.text)
        if 'errorCode' in app_resp:
            print("ERROR: " + app_resp['errorSummary'], "Error Code ", app_resp['errorCode'])
            sys.exit(2)
        return app_resp

    def get_app(self,login_resp):
        """ gets a list of available apps and
        ask the user to select the app they want
        to assume a roles for and returns the selection"""
        app_resp = self.get_app_links(login_resp)
        print ("Pick an app:")
        # print out the apps and let the user select
        for i, app in enumerate(app_resp):
            print ('[',i,']', app["label"])
        selection = input("Selection: ")
        # make sure the choice is valid
        if int(selection) > len(app_resp):
            print ("You selected an invalid selection")
            sys.exit(1)
        return app_resp[int(selection)]["label"]

    def get_role(self,login_resp,aws_appname):
        """ gets a list of available roles and
        ask the user to select the app they want
        to assume and returns the selection"""
        # get available roles for the AWS app
        headers = self.get_headers()
        user_id = login_resp['_embedded']['user']['id']
        response = requests.get(self.idp_entry_url + '/apps/?filter=user.id+eq+\"' +
            user_id + '\"&expand=user/' + user_id,headers=headers, verify=True)
        role_resp = json.loads(response.text)
        # Check if this is a valid response
        if 'errorCode' in role_resp:
            print("ERROR: " + role_resp['errorSummary'], "Error Code ", role_resp['errorCode'])
            sys.exit(2)
        # print out roles for the app and let the uesr select
        for app in role_resp:
            if app['label'] == aws_appname:
                print ("Pick a role:")
                roles = app['_embedded']['user']['profile']['samlRoles']
                for i, role in enumerate(roles):
                    print ('[',i,']:', role)
                selection = input("Selection: ")
                # make sure the choice is valid
                if int(selection) > len(roles):
                    print ("You selected an invalid selection")
                    sys.exit(1)
                return roles[int(selection)]

    def get_app_url(self,login_resp,aws_appname):
        """ return the app link json for select aws app """
        app_resp = self.get_app_links(login_resp)
        for app in app_resp:
            #print(app['label'])
            if(app['label'] == 'AWS_API'):
                print(app['linkUrl'])
            if app['label'] == aws_appname:
                return app
        print("ERROR app not found:", aws_appname)
        sys.exit(2)

    def get_idp_arn(self,app_id):
        """ return the PrincipalArn based on the app instance id """
        headers = self.get_headers()
        response = requests.get(self.idp_entry_url + '/apps/' + app_id ,headers=headers, verify=True)
        app_resp = json.loads(response.text)
        return app_resp['settings']['app']['identityProviderArn']
