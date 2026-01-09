# gimme-aws-creds - Development Guide

## Prerequisites

- **Python**: 3.7 or higher
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
├── config.py        # Configuration handling
├── okta_classic.py  # Okta Classic auth flow
├── okta_identity_engine.py  # OIE auth flow
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

3. Update `_build_factor_name` for display

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

1. Update version in `gimme_aws_creds/__init__.py` and `setup.py`
2. Update CHANGELOG (if maintained)
3. Create GitHub release with tag
4. Package published to PyPI via CI/CD
