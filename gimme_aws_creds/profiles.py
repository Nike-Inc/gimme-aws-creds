"""
    The Profile class generates a profile name from the cred_profile configuration parameter.
"""
class Profile:
    def __init__(self, cred_profile, include_path):
        self.cred_profile = cred_profile
        self.include_path = include_path

    def canonicalize(self):
        lc_profile = self.cred_profile.lower()
        if lc_profile in ['default', 'role', 'acc'] or self._is_delimited(lc_profile):
            return lc_profile
        else:
            return self.cred_profile

    def _is_delimited(self, lc_profile):
        if len(lc_profile)==8 and lc_profile.startswith('acc') and lc_profile.endswith('role'):
            return lc_profile[3]
        return False

    def name_for(self, account, role_name, path='/'):
        lc_profile = self.cred_profile.lower()
        if lc_profile == 'default':
            return 'default'
        elif lc_profile == 'role':
            return role_name
        elif lc_profile == 'acc':
            return account
        elif delimiter := self._is_delimited(lc_profile):
            if self.include_path:
                role_name = ''.join([path, role_name])
            return delimiter.join([account, role_name])
        else:
            return self.cred_profile
