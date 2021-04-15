"""
Copyright 2018-present Krzysztof Nazarewski.
Licensed under the Apache License, Version 2.0 (the "License");
You may not use this file except in compliance with the License.
You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and* limitations under the License.*
"""
import sys

from . import ui


class GimmeAWSCredsExitBase(Exception):
    def __init__(self, message, return_code, result=None):
        """
        :type message: str
        :type return_code: int
        :type result: str
        """
        super().__init__(message, return_code)
        self.message = message
        self.return_code = return_code
        self.result = result

    def handle(self):
        self.handle_message()
        self.handle_result()
        self.exit()

    def handle_message(self):
        if self.message:
            ui.default.info(self.message)

    def handle_result(self):
        if self.result is not None:
            ui.default.result(self.result)

    def exit(self):
        sys.exit(self.return_code)


class GimmeAWSCredsExitSuccess(GimmeAWSCredsExitBase):
    def __init__(self, message='', return_code=0, result=''):
        super().__init__(message, return_code, result)


class GimmeAWSCredsExitError(GimmeAWSCredsExitBase):
    def __init__(self, message='ERROR', return_code=1, output=''):
        super().__init__(message, return_code, output)


class GimmeAWSCredsExceptionBase(Exception):
    pass


class GimmeAWSCredsError(GimmeAWSCredsExceptionBase, GimmeAWSCredsExitError):
    pass


class GimmeAWSCredsMFAEnrollStatus(GimmeAWSCredsError):
    def __init__(self):
        super().__init__("You must enroll in MFA before using this tool.", 2)


class NoFIDODeviceFoundError(Exception):
    pass


class FIDODeviceTimeoutError(Exception):
    pass


class FIDODeviceError(Exception):
    pass
