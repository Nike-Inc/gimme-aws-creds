# Lambda Service for gimme-aws-creds

### Summary
This service interacts with the Okta User and App APIs on behalf of the gimme-aws-creds CLI client.  It removes the need for an Okta API key within the gimme-aws-creds client and filters the API results to just the data necessary for requesting AWS credentials.

### Dependencies
- Python 2.7 (https://www.python.org)
- okta-sdk-python v0.4+ (https://github.com/okta/okta-sdk-python)

### Environmental Variables
To run the lambda, you'll need to pass in two environment variables:
- `OKTA_API_KEY` A read-only Okta API key that will be used for the User and Apps APIs
- `OKTA_ORG_URL` The Okta domain URL to use for API calls (e.g. https://example.okta.com)

### OAuth Token Authorizer
Developing the OAuth Token authorizer and deployment process for the Lambda is left up to you.  For an example of how to write an Authorizer and deploy an API using the [Serverless](https://serverless.com/) framework, take a look at this [Github repo](https://github.com/pmcdowell-okta/oauth-jwt-serverless-aws-apigateway).
