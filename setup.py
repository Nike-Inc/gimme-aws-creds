from setuptools import setup, find_packages

import gimme_aws_creds

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='gimme aws creds',
    version=gimme_aws_creds.version,
    install_requires=requirements,
    author='Eric Pierce',
    author_email='eric.pierce@nike.com',
    description="A CLI to get temporary AWS credentials from Okta",
    url='https://github.com/Nike-Inc/gimme-aws-creds',
    long_description=open("LONG_DESCRIPTION.md").read(),
    python_requires=">=3.7",
    license='Apache License, v2.0',
    packages=find_packages(exclude=('tests', 'docs')),
    test_suite="tests",
    scripts=['bin/gimme-aws-creds', 'bin/gimme-aws-creds.cmd', 'bin/gimme-aws-creds-autocomplete.sh'],
    classifiers=[
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: Apache Software License'
    ]
)
