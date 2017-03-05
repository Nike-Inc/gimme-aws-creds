from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='gimme aws creds',
    version='0.1.1',
    install_requires=requirements,
    author='Ann Wallace',
    author_email='ann.wallace@nike.com',
    description="A CLI to get temporary AWS credentials from Okta",
    packages=find_packages(exclude=('tests', 'docs')),
    test_suite="tests",
  )
