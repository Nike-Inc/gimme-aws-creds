import json
import os
import sys

from okta.framework.ApiClient import ApiClient
from okta.framework.OktaError import OktaError


def aws_account_info(event, context):
    # We need access to the entire JSON response from the Okta APIs, so we need to
    # use the low-level ApiClient instead of UsersClient and AppInstanceClient
    usersClient = ApiClient(os.environ['OKTA_ORG_URL'],
                            os.environ['OKTA_API_KEY'],
                            pathname='/api/v1/users')
    appClient = ApiClient(os.environ['OKTA_ORG_URL'],
                          os.environ['OKTA_API_KEY'],
                          pathname='/api/v1/apps')

    # Get User information
    username = event['requestContext']['authorizer']['principalId']
    try:
        result = usersClient.get_path('/{0}'.format(username))
        user = result.json()
    except OktaError as e:
        if e.error_code == 'E0000007':
            statusCode = 404
        else:
            statusCode = 500
        return {
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin' : '*',
                'Access-Control-Allow-Credentials' : True
            },
            "statusCode": statusCode,
            "body": e.error_summary
        }

    # Get a list of apps for this user and include extended info about the user
    params = {
        'limit': 200,
        'filter': 'user.id+eq+%22' + user['id'] + '%22&expand=user%2F' + user['id']
    }

    try:
        # Get first page of results
        result = usersClient.get_path('/{0}/appLinks'.format(user['id']))
        final_result = result.json()

        # Loop through other pages
        while 'next' in result.links:
            result = appClient.get(result.links['next']['url'])
            final_result = final_result + result.json()
    except OktaError as e:
        if e.error_code == 'E0000007':
            statusCode = 404
        else:
            statusCode = 500
        return {
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin' : '*',
                'Access-Control-Allow-Credentials' : True
            },
            "statusCode": statusCode,
            "body": e.error_summary
        }

    # Loop through the list of apps and filter it down to just the info we need
    appList = []
    for app in final_result:
        # All AWS connections have the same app name
        if (app['appName'] == 'amazon_aws'):
            newAppEntry = {}
            newAppEntry['id'] = app['id']
            newAppEntry['name'] = app['label']
            newAppEntry['links'] = {}
            newAppEntry['links']['appLink'] = app['linkUrl']
            newAppEntry['links']['appLogo'] = app['logoUrl']
            appList.append(newAppEntry)

    response = {
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin' : '*',
            'Access-Control-Allow-Credentials' : True
        },
        "statusCode": 200,
        "body": json.dumps(appList)
    }

    return response

def main():
    event = {
        'requestContext': {
            'authorizer': {
                'principalId' : sys.argv[1]
            }
        }
    }

    print(aws_account_info(event, {}))

if __name__ == "__main__": main()
