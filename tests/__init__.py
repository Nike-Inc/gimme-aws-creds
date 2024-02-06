import os


def read_fixture(file_name):
    """Read a fixture file"""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', file_name)
    with open(fixture_path, 'r', encoding='utf-8') as file:
        return file.read()
