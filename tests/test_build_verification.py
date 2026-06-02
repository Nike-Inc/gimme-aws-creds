"""Automated tests for pip build and installation verification.

These tests verify that the package can be built and installed correctly,
ensuring build verification is repeatable and automated.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestBuildVerification(unittest.TestCase):
    """Test that package builds and installs correctly"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.project_root = Path(__file__).parent.parent
        cls.setup_py = cls.project_root / "setup.py"
        cls.pyproject_toml = cls.project_root / "pyproject.toml"
        cls.requirements_txt = cls.project_root / "requirements.txt"

    def test_setup_py_exists(self):
        """Verify setup.py exists and is readable"""
        self.assertTrue(self.setup_py.exists(), "setup.py must exist")
        self.assertTrue(self.setup_py.is_file(), "setup.py must be a file")

    def test_pyproject_toml_exists(self):
        """Verify pyproject.toml exists for PEP 517 build"""
        self.assertTrue(self.pyproject_toml.exists(), "pyproject.toml must exist")
        self.assertTrue(self.pyproject_toml.is_file(), "pyproject.toml must be a file")

    def test_requirements_txt_exists(self):
        """Verify requirements.txt exists"""
        self.assertTrue(self.requirements_txt.exists(), "requirements.txt must exist")
        self.assertTrue(self.requirements_txt.is_file(), "requirements.txt must be a file")

    def test_setup_py_python_requires(self):
        """Verify python_requires is set correctly"""
        with open(self.setup_py) as f:
            content = f.read()
            # Python 3.10+ required for boto3>=1.42.24 with urllib3>=2.6.3
            self.assertIn('python_requires=">=3.10"', content,
                         "setup.py must specify python_requires >= 3.10")

    def test_setup_py_scripts_included(self):
        """Verify scripts are included in setup.py"""
        with open(self.setup_py) as f:
            content = f.read()
            self.assertIn("bin/gimme-aws-creds", content,
                         "setup.py must include bin/gimme-aws-creds script")
            self.assertIn("bin/gimme-aws-creds.cmd", content,
                         "setup.py must include bin/gimme-aws-creds.cmd script")
            self.assertIn("bin/gimme-aws-creds-autocomplete.sh", content,
                         "setup.py must include autocomplete script")

    def test_pyproject_toml_build_system(self):
        """Verify pyproject.toml has correct build system"""
        with open(self.pyproject_toml) as f:
            content = f.read()
            self.assertIn("setuptools", content,
                         "pyproject.toml must specify setuptools")
            self.assertIn("setuptools-rust", content,
                         "pyproject.toml must specify setuptools-rust for fido2")

    def test_requirements_txt_has_dependencies(self):
        """Verify requirements.txt contains expected dependencies"""
        with open(self.requirements_txt) as f:
            content = f.read()
            required_deps = [
                "boto3",
                "requests",
                "urllib3",
                "okta",
                "keyring",
                "fido2",
                "beautifulsoup4",
                "html5lib",
                "pyjwt",
                "furl"
            ]
            for dep in required_deps:
                self.assertIn(dep.lower(), content.lower(),
                             f"requirements.txt must include {dep}")

    def test_requirements_txt_has_version_bounds(self):
        """Verify requirements.txt uses version bounds"""
        with open(self.requirements_txt) as f:
            lines = f.read().splitlines()
            # Check that at least some dependencies have version constraints
            version_constrained = [line for line in lines if ">=" in line or "==" in line]
            self.assertGreater(len(version_constrained), 5,
                             "requirements.txt should have version constraints on most dependencies")

    def test_package_structure_exists(self):
        """Verify package directory structure exists"""
        package_dir = self.project_root / "gimme_aws_creds"
        self.assertTrue(package_dir.exists(), "gimme_aws_creds package directory must exist")
        self.assertTrue(package_dir.is_dir(), "gimme_aws_creds must be a directory")
        
        # Check for key modules
        key_modules = ["__init__.py", "main.py", "config.py", "aws.py"]
        for module in key_modules:
            module_path = package_dir / module
            self.assertTrue(module_path.exists(),
                          f"gimme_aws_creds/{module} must exist")

    def test_bin_scripts_exist(self):
        """Verify bin scripts exist"""
        bin_dir = self.project_root / "bin"
        self.assertTrue(bin_dir.exists(), "bin directory must exist")
        
        scripts = [
            "gimme-aws-creds",
            "gimme-aws-creds.cmd",
            "gimme-aws-creds-autocomplete.sh"
        ]
        for script in scripts:
            script_path = bin_dir / script
            self.assertTrue(script_path.exists(),
                          f"bin/{script} must exist")

    @unittest.skipIf(os.getenv("SKIP_BUILD_TESTS") == "1",
                     "Skipping build tests (set SKIP_BUILD_TESTS=1)")
    def test_pip_install_dry_run(self):
        """Verify pip install dry-run succeeds"""
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", ".", "--dry-run"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=60
        )
        self.assertEqual(result.returncode, 0,
                        f"pip install --dry-run should succeed. Error: {result.stderr}")

    def test_setup_py_version_format(self):
        """Verify version string is valid"""
        with open(self.setup_py) as f:
            content = f.read()
            # Check that version is set (format can vary: 2.8.2-pre, 2.8.2rc0, etc.)
            self.assertIn("version=", content,
                         "setup.py must specify version")
            # Version should not be empty
            import re
            version_match = re.search(r"version=['\"]([^'\"]+)['\"]", content)
            if version_match:
                version = version_match.group(1)
                self.assertGreater(len(version), 0,
                                 "Version string must not be empty")


class TestInstallationVerification(unittest.TestCase):
    """Test that installed package works correctly"""

    def test_cli_help_available(self):
        """Verify CLI help command works (if package is installed)"""
        # This test only runs if gimme-aws-creds is installed
        try:
            result = subprocess.run(
                ["gimme-aws-creds", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Help should succeed with exit code 0
            self.assertEqual(result.returncode, 0,
                          f"gimme-aws-creds --help should succeed. Error: {result.stderr}")
            # Help output should contain expected text
            self.assertIn("usage:", result.stdout.lower() or result.stderr.lower(),
                         "Help output should contain usage information")
        except FileNotFoundError:
            self.skipTest("gimme-aws-creds not installed (run 'pip install -e .' first)")

    def test_cli_version_available(self):
        """Verify CLI version command works (if package is installed)"""
        try:
            result = subprocess.run(
                ["gimme-aws-creds", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            # Version should succeed with exit code 0
            self.assertEqual(result.returncode, 0,
                          f"gimme-aws-creds --version should succeed. Error: {result.stderr}")
            # Version output should contain version number
            output = result.stdout or result.stderr
            self.assertRegex(output, r"\d+\.\d+\.\d+",
                           "Version output should contain version number")
        except FileNotFoundError:
            self.skipTest("gimme-aws-creds not installed (run 'pip install -e .' first)")


if __name__ == "__main__":
    unittest.main()
