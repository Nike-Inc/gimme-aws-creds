import tempfile
from abc import ABC

from gimme_aws_creds import ui


class MockUserInterface(ui.UserInterface, ABC):
    def __init__(self, environ=None, argv=None):
        super().__init__(environ=environ or {}, argv=argv or [])
        self.HOME = tempfile.mkdtemp()
