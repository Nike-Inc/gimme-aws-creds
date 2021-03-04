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
import builtins
import getpass
import os
import sys


class UserInterface:
    def __init__(self, environ=os.environ, argv=None):
        if argv is None:
            argv = sys.argv

        self.environ = environ.copy()
        self.environ_bkp = None
        self.argv = argv[:]
        self.argv_bkp = None
        self.args = self.argv[1:]
        with self:
            self.HOME = os.path.expanduser('~')

    def result(self, result):
        """handles output lines
        :type result: str
        """
        raise NotImplementedError()

    def prompt(self, message):
        """handles input's prompt message, but does not ask for input
        :type message: str
        """
        raise NotImplementedError()

    def message(self, message):
        """handles messages meant for user interactions
        :type message: str
        """
        raise NotImplementedError()

    def read_input(self, hidden=False):
        """returns user input
        :rtype: str
        """
        raise NotImplementedError()

    def notify(self, message):
        """handles messages meant for user notifications
        :type message: str
        """
        raise NotImplementedError()

    def input(self, message=None, hidden=False):
        """handles asking for user input, calls prompt() then read_input()
        :type message: str
        :rtype: str
        """
        self.prompt(message)
        return self.read_input(hidden)

    def info(self, message):
        """handles messages meant for info
        :type message: str
        """
        self.notify(message)

    def warning(self, message):
        """handles messages meant for warnings
        :type message: str
        """
        self.notify(message)

    def error(self, message):
        """handles messages meant for errors
        :type message: str
        """
        self.notify(message)

    def __enter__(self):
        self.environ_bkp = os.environ
        self.argv_bkp = sys.argv

        os.environ = self.environ
        sys.argv = sys.argv[:1] + self.args
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.environ = self.environ_bkp
        sys.argv = self.argv_bkp
        self.environ_bkp = None
        self.argv_bkp = None


class CLIUserInterface(UserInterface):
    def result(self, result):
        builtins.print(result, file=sys.stdout)

    def prompt(self, message=None):
        if message is not None:
            builtins.print(message, file=sys.stderr, end='')
            sys.stderr.flush()

    def message(self, message):
        builtins.print(message, file=sys.stderr)

    def read_input(self, hidden=False):
        return getpass.getpass('') if hidden else builtins.input()

    def notify(self, message):
        builtins.print(message, file=sys.stderr)


cli = CLIUserInterface()
default = cli
