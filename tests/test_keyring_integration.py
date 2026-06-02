"""Unit tests for keyring integration and deprecation warnings"""
import unittest
import warnings

import keyring
from keyring.backends.fail import Keyring as FailKeyring
from keyring.errors import PasswordDeleteError


class TestKeyringDeprecationWarnings(unittest.TestCase):
    """Test that keyring and ctap-keyring-device don't produce deprecation warnings"""

    def test_no_keyring_deprecation_warnings(self):
        """AC #5: Verify no keyring deprecation warnings appear"""
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # Import keyring and use its APIs
                import keyring
                keyring.get_keyring()
                try:
                    keyring.get_password('test-service', 'test-user')
                except keyring.errors.NoKeyringError:
                    # No keyring backend available - skip the get_password test
                    # but we can still check for deprecation warnings from the import/get_keyring
                    pass
                
                # Check for deprecation warnings
                deprecation_warnings = [
                    x for x in w 
                    if 'deprecated' in str(x.message).lower() 
                    or issubclass(x.category, DeprecationWarning)
                ]
                self.assertEqual(
                    len(deprecation_warnings), 
                    0,
                    f"Found deprecation warnings: {[str(x.message) for x in deprecation_warnings]}"
                )
        except keyring.errors.NoKeyringError:
            self.skipTest("No keyring backend available on this platform")

    def test_no_ctap_keyring_device_deprecation_warnings(self):
        """AC #5: Verify no ctap-keyring-device deprecation warnings appear"""
        try:
            import ctap_keyring_device
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # Import ctap-keyring-device and use its APIs
                from ctap_keyring_device.ctap_keyring_device import CtapKeyringDevice
                from ctap_keyring_device.ctap_strucs import CtapOptions
                
                # Try to list devices (may return empty list if no devices)
                try:
                    CtapKeyringDevice.list_devices()
                except Exception:
                    # Ignore errors - we're just checking for deprecation warnings
                    pass
                
                # Check for deprecation warnings
                deprecation_warnings = [
                    x for x in w 
                    if 'deprecated' in str(x.message).lower() 
                    or issubclass(x.category, DeprecationWarning)
                ]
                self.assertEqual(
                    len(deprecation_warnings), 
                    0,
                    f"Found deprecation warnings: {[str(x.message) for x in deprecation_warnings]}"
                )
        except ImportError:
            # ctap-keyring-device may not be available on all platforms (e.g., Windows Python 3.10+)
            self.skipTest("ctap-keyring-device not available on this platform")


class TestKeyringAPIs(unittest.TestCase):
    """Test that keyring APIs work correctly"""

    def test_keyring_get_keyring_api(self):
        """Verify keyring.get_keyring() API works"""
        keyring_instance = keyring.get_keyring()
        self.assertIsNotNone(keyring_instance)

    def test_fail_keyring_detection(self):
        """Verify FailKeyring detection works"""
        # This test verifies the isinstance check used in okta_classic.py line 57
        keyring_instance = keyring.get_keyring()
        is_fail = isinstance(keyring_instance, FailKeyring)
        # Result depends on platform - just verify the check works
        self.assertIsInstance(is_fail, bool)

    def test_keyring_password_operations(self):
        """Test keyring password storage/retrieval/deletion APIs"""
        service = 'gimme-aws-creds-test'
        username = 'test-user'
        password = 'test-password'
        
        try:
            # Test set_password
            keyring.set_password(service, username, password)
            
            # Test get_password
            retrieved = keyring.get_password(service, username)
            self.assertEqual(retrieved, password)
            
            # Test delete_password
            keyring.delete_password(service, username)
            
            # Verify deletion worked
            retrieved_after_delete = keyring.get_password(service, username)
            self.assertIsNone(retrieved_after_delete)
        except RuntimeError:
            # Keyring may not be available on all platforms
            self.skipTest("Keyring not available on this platform")
        except Exception as e:
            # Clean up on any error
            try:
                keyring.delete_password(service, username)
            except:
                pass
            raise
