"""Unit tests for gimme_aws_creds.config.Config"""
import argparse
import unittest

from mock import patch
from nose.tools import assert_equals

from gimme_aws_creds.config import Config
from gimme_aws_creds import version


class TestConfig(unittest.TestCase):
    """Class to test Config Class.
       Mock is used to mock external calls"""

    def setUp(self):
        """Set up for the unit tests"""
        self.config = Config()

    def tearDown(self):
        """Run Clean Up"""
        self.config.clean_up()

    @patch('argparse.ArgumentParser.parse_args',
           return_value=argparse.Namespace(username='ann', configure=False, profile=None, insecure=False, resolve=None, mfa_code=None, register_device=False))
    def test_get_args_username(self, mock_arg):
        """Test to make sure username gets returned"""
        self.config.get_args()
        assert_equals(self.config.username, 'ann')


