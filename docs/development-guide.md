# gimme-aws-creds - Development Guide

## Prerequisites

- **Python**: 3.10 or higher
- **pip**: Latest version recommended
- **Git**: For version control

### Optional
- **Nix**: For reproducible builds (flake.nix provided)
- **Docker**: For containerized builds

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/Nike-Inc/gimme-aws-creds.git
cd gimme-aws-creds
```

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows
```

### Install Dependencies

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements_dev.txt

# Install package in editable mode
pip install -e .
```

### Using Nix (Alternative)

```bash
# With flakes
nix develop

# Without flakes
nix-shell
```

## Running the Tool

### From Source

```bash
# Direct invocation
python -m gimme_aws_creds.main

# Via installed entry point
gimme-aws-creds
```

### Configuration

First-time setup:
```bash
gimme-aws-creds --action-configure
```

This creates `~/.okta_aws_login_config` with your settings.

## Running Tests

### All Tests

```bash
pytest -vv tests
```

### Specific Test File

```bash
pytest -vv tests/test_main.py
```

### With Coverage

```bash
pytest --cov=gimme_aws_creds tests/
```

## Code Style

The project follows standard Python conventions:

- PEP 8 style guidelines
- Docstrings for public methods
- Type hints encouraged but not required
- Max line length: ~120 characters

## Project Structure

```
gimme_aws_creds/
├── main.py          # Start here - main orchestration
├── common.py        # Shared utilities (HTTP sessions, SAML parsing, OktaHttpMixin)
├── config.py        # Configuration handling
├── okta_classic.py  # Okta Classic auth flow (inherits OktaHttpMixin)
├── okta_identity_engine.py  # OIE auth flow (inherits OktaHttpMixin)
├── alibaba_cloud.py # AliCloud RAM credential support
└── ...
```

## Making Changes

### Adding a New MFA Factor

1. Add handler method in `okta_classic.py`:
   ```python
   def _login_send_new_factor(self, state_token, factor):
       # Implementation
   ```

2. Update `_login_multi_factor` dispatch:
   ```python
   elif factor['factorType'] == 'new_factor':
       return self._login_send_new_factor(state_token, factor)
   ```

3. Use `_build_auth_flow_result(response_data)` to extract the `stateToken`/`sessionToken` from the MFA response consistently

4. Update `_build_factor_name` for display

### Adding Configuration Options

1. Add default in `Config.update_config_file`:
   ```python
   defaults = {
       'new_option': 'default_value',
       ...
   }
   ```

2. Add CLI argument if needed in `Config.get_args`

3. Add prompt method for interactive configuration

### Adding Environment Variable Support

Update `GimmeAWSCreds.envvar_list` and optionally `envvar_conf_map`:
```python
envvar_list = [
    ...
    'NEW_ENVVAR',
]

envvar_conf_map = {
    ...
    'NEW_ENVVAR': 'config_key',
}
```

## Testing Guidelines

### Writing Tests

- Use `user_interface_mock.py` for UI mocking
- Use fixtures in `tests/fixtures/` for HTML responses
- Mock external HTTP calls with `unittest.mock` or `responses`
- Use shared utilities from `tests/helpers.py`:
  - `captured_output()` context manager for capturing stdout/stderr
  - `make_args(**overrides)` factory for building `argparse.Namespace` test objects

### Test Structure

```python
def test_feature_name(self):
    # Arrange
    mock_ui = MockUserInterface(...)
    client = SomeClient(mock_ui, ...)
    
    # Act
    result = client.some_method()
    
    # Assert
    self.assertEqual(expected, result)
```

### Test Organization

| Test File | Coverage |
|-----------|----------|
| `test_main.py` | `GimmeAWSCreds` class methods |
| `test_config.py` | Configuration parsing and profiles |
| `test_aws_resolver.py` | SAML parsing, role enumeration |
| `test_okta_classic_client.py` | Classic auth flow and MFA |
| `test_okta_identity_engine_client.py` | OIE auth flow |
| `test_alibaba_cloud.py` | AliCloud credential handling |
| `test_duo_universal_client.py` | DUO Universal Prompt |
| `test_bug_fixes.py` | Regression tests for critical bug fixes |
| `test_build_verification.py` | Import and shared utility verification |
| `test_registered_authenticators.py` | FIDO registry |
| `test_keyring_integration.py` | Keyring storage |

## Building

### Python Package

```bash
python -m build
```

### Docker Image

```bash
docker build -t gimme-aws-creds .
```

## Debugging Tips

### Enable Verbose Output

The tool outputs messages to stderr and results to stdout:
```bash
gimme-aws-creds 2>&1 | tee debug.log
```

### Common Issues

1. **SSL Errors**: Use `--insecure` flag (not recommended for production)
2. **MFA Timeout**: Check factor configuration in Okta
3. **Invalid Session**: Clear device token from config

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Code of Conduct
- Contributor License Agreement
- Pull request process

## Release Process

### 1. Prepare the Release

1. Update version in `gimme_aws_creds/__init__.py` and `setup.py`
   - Remove `-pre` suffix for production releases
   - Follow semantic versioning (MAJOR.MINOR.PATCH)
   
2. Update CHANGELOG (if maintained)
   - Document all changes, bug fixes, and new features
   
3. Commit version changes:
   ```bash
   git add gimme_aws_creds/__init__.py setup.py
   git commit -m "Bump version to X.Y.Z"
   git push origin main
   ```

### 2. Create GitHub Release

1. Create and push a git tag:
   ```bash
   git tag -a vX.Y.Z -m "Release version X.Y.Z"
   git push origin vX.Y.Z
   ```

2. Create a GitHub release:
   - Go to https://github.com/Nike-Inc/gimme-aws-creds/releases/new
   - Select the tag you just created
   - Add release notes (copy from CHANGELOG)
   - Publish the release

3. Verify PyPI deployment:
   - CI/CD will automatically publish to PyPI
   - Check https://pypi.org/project/gimme-aws-creds/

### 3. Update Homebrew Formula

Homebrew formulas are maintained in the [homebrew-core](https://github.com/Homebrew/homebrew-core) repository. After a new version is released to PyPI, the Homebrew formula needs to be updated.

#### Option A: Automated Update (Recommended)

Homebrew maintainers often update popular formulas automatically when new versions are detected. Wait 24-48 hours to see if the formula is auto-updated.

#### Option B: Manual Update

If the formula isn't automatically updated, you can submit an update yourself:

1. **Set up your environment:**
   ```bash
   # Ensure you have the latest Homebrew
   brew update
   
   # Tap homebrew-core for editing (only needed once)
   export HOMEBREW_NO_INSTALL_FROM_API=1
   brew tap --force homebrew/core
   ```

2. **Locate the formula:**
   ```bash
   brew edit gimme-aws-creds
   ```
   
   This opens the formula file, typically located at:
   `$(brew --repository homebrew/core)/Formula/g/gimme-aws-creds.rb`

3. **Update the formula:**
   
   The formula will look something like this:
   ```ruby
   class GimmeAwsCreds < Formula
     include Language::Python::Virtualenv

     desc "CLI to retrieve AWS credentials from Okta"
     homepage "https://github.com/Nike-Inc/gimme-aws-creds"
     url "https://files.pythonhosted.org/packages/.../gimme-aws-creds-X.Y.Z.tar.gz"
     sha256 "abc123..."
     license "Apache-2.0"

     depends_on "python@3.11"

     resource "dependency-name" do
       url "https://files.pythonhosted.org/packages/.../dependency-X.Y.Z.tar.gz"
       sha256 "def456..."
     end

     def install
       virtualenv_install_with_resources
     end

     test do
       assert_match version.to_s, shell_output("#{bin}/gimme-aws-creds --version")
     end
   end
   ```

   **Update these fields:**
   
   a. **version**: Update the version number
   
   b. **url**: Update to the new PyPI release URL
   ```ruby
   url "https://files.pythonhosted.org/packages/.../gimme-aws-creds-X.Y.Z.tar.gz"
   ```
   
   c. **sha256**: Calculate the new SHA256 checksum:
   ```bash
   # Download the new release tarball from PyPI
   curl -L -o gimme-aws-creds-X.Y.Z.tar.gz \
     https://files.pythonhosted.org/packages/.../gimme-aws-creds-X.Y.Z.tar.gz
   
   # Calculate SHA256
   shasum -a 256 gimme-aws-creds-X.Y.Z.tar.gz
   ```
   
   d. **resources**: Update dependency versions if `requirements.txt` changed
   - List current dependencies: `cat requirements.txt`
   - Use `brew bump-formula-pr --python-resources-from-wheel` (see below)

4. **Test the formula locally:**
   ```bash
   # Audit the formula for issues
   brew audit --strict --online gimme-aws-creds
   
   # Install from your modified formula
   brew reinstall --build-from-source gimme-aws-creds
   
   # Run the formula's test
   brew test gimme-aws-creds
   
   # Verify it works
   gimme-aws-creds --version
   ```

5. **Create a Pull Request:**
   
   **Automated approach (recommended):**
   ```bash
   # This command does most of the work automatically
   brew bump-formula-pr \
     --url="https://files.pythonhosted.org/packages/.../gimme-aws-creds-X.Y.Z.tar.gz" \
     --sha256="<calculated-sha256>" \
     gimme-aws-creds
   ```
   
   **Manual approach:**
   ```bash
   # Navigate to homebrew-core
   cd $(brew --repository homebrew/core)
   
   # Create a feature branch
   git checkout -b gimme-aws-creds-X.Y.Z
   
   # Stage your changes
   git add Formula/g/gimme-aws-creds.rb
   
   # Commit with a descriptive message
   git commit -m "gimme-aws-creds X.Y.Z"
   
   # Push to your fork (you'll need to fork homebrew-core first)
   git push <your-fork> gimme-aws-creds-X.Y.Z
   
   # Open a pull request on GitHub
   # Go to: https://github.com/Homebrew/homebrew-core/compare
   ```

6. **Pull Request Guidelines:**
   - Title: `gimme-aws-creds X.Y.Z`
   - Description should include:
     - Link to the release notes
     - Confirmation that tests pass
     - Any notable changes
   - The PR will be reviewed by Homebrew maintainers
   - Automated tests will run on macOS and Linux

#### Homebrew Formula Best Practices

- **Version conflicts**: If the formula name conflicts with another package, it may need a vendor prefix (e.g., `nike-gimme-aws-creds`)
- **Testing**: Always run `brew test` before submitting
- **Audit**: Run `brew audit --strict --online` to catch issues
- **Python resources**: Homebrew bundles all Python dependencies as "resources" in the formula
- **Documentation**: See [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook) for advanced topics

#### Troubleshooting Homebrew Updates

**Common issues:**

1. **Checksum mismatch**: Recalculate the SHA256 checksum
2. **Missing dependencies**: Update the Python resources section
3. **Test failures**: Check the formula's `test` block
4. **Build failures**: Verify the package installs correctly from PyPI

**Verification:**
```bash
# Check installed version
brew info gimme-aws-creds

# Check for outdated formula
brew outdated gimme-aws-creds

# Check formula validity
brew audit gimme-aws-creds
```

### 4. Post-Release Tasks

1. **Verify installations:**
   ```bash
   # PyPI
   pip install --upgrade gimme-aws-creds
   gimme-aws-creds --version
   
   # Homebrew (after formula is merged)
   brew upgrade gimme-aws-creds
   gimme-aws-creds --version
   ```

2. **Update documentation:**
   - Ensure README.md installation instructions are current
   - Update any version-specific documentation

3. **Announce the release:**
   - Notify users through appropriate channels

4. **Prepare for next development cycle:**
   ```bash
   # Bump version to next -pre version
   # e.g., if you just released 2.8.2, bump to 2.8.3-pre
   ```

### Release Checklist

- [ ] Version updated in `__init__.py` and `setup.py`
- [ ] CHANGELOG updated
- [ ] Version changes committed and pushed
- [ ] Git tag created and pushed
- [ ] GitHub release created
- [ ] PyPI package published (automatic via CI/CD)
- [ ] Homebrew formula updated (may be automatic)
- [ ] Installation verified on PyPI
- [ ] Installation verified on Homebrew
- [ ] Documentation updated
- [ ] Next pre-release version set

### Additional Resources

- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Python for Formula Authors](https://docs.brew.sh/Python-for-Formula-Authors)
- [How to Open a Homebrew Pull Request](https://docs.brew.sh/How-To-Open-a-Homebrew-Pull-Request)
- [PyPI Publishing Guide](https://packaging.python.org/tutorials/packaging-projects/)
