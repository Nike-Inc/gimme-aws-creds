"""
Copyright 2018-present Engie SA / Synetis.
Licensed under the Apache License, Version 2.0 (the "License");
You may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and* limitations under the License.*
"""
import base64
import xml.etree.ElementTree as ET

import gimme_aws_creds.common as commondef
from . import errors


class DefaultResolver(object):
    """
       The Aws Client Class performs post request on AWS sign-in page
       to fetch friendly names/alias for account and IAM roles
    """

    def __init__(self, verify_ssl_certs=True):
        return

    def _enumerate_saml_roles(self, assertion, saml_target_url):
        """ using the assertion to fetch aws sign-in page, parse it and return aws sts creds """
        role_pairs = []
        root = ET.fromstring(base64.b64decode(assertion))
        for saml2_attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
            if saml2_attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role':
                for saml2_attribute_value in saml2_attribute.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
                    role_pairs.append(saml2_attribute_value.text)

        # Normalize pieces of string; order may vary per AWS sample
        result = []
        for role_pair in role_pairs:
            idp, role = None, None
            for field in role_pair.split(','):
                if 'saml-provider' in field:
                    idp = field
                elif 'role' in field:
                    role = field
            if not idp or not role:
                raise errors.GimmeAWSCredsError('Parsing error on {}'.format(role_pair))
            else:
                result.append(commondef.RoleSet(idp=idp, role=role, friendly_account_name="", friendly_role_name=""))

        return result

    def _display_role(self, roles):
        """ gets a list of available roles and
        asks the user to select the role they want to assume
        """
        # Gather the roles available to the user.
        role_strs = []
        for i, role in enumerate(roles):
            if not role:
                continue
            role_strs.append('[{}] {}'.format(i, role.role))

        return role_strs
