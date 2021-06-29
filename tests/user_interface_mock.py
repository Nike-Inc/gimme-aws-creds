import tempfile

from gimme_aws_creds import ui


class MockUserInterface(ui.UserInterface):
    def result(self, result):
        pass

    def prompt(self, message):
        pass

    def message(self, message):
        pass

    def read_input(self, hidden=False):
        pass

    def notify(self, message):
        pass

    def __init__(self, environ=None, argv=None):
        super().__init__(environ=environ or {}, argv=argv or [])
        self.HOME = tempfile.mkdtemp()
