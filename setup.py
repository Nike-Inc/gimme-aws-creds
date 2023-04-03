from setuptools import setup, find_packages
from setuptools.command.install import install
from subprocess import call

import gimme_aws_creds

class gimme_aws_creds_installer(install):
    ''' Superclass of the installer, adding a post-install script.
    '''
    def __post_install(self, dir: str):
        call(['./setup_autocomplete.sh'])

    def run(self):
        install.run(self)
        self.execute(self.__post_install, (self.install_lib,), msg="Installing autocomplete")


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
    python_requires=">=3.6",
    license='Apache License, v2.0',
    packages=find_packages(exclude=('tests', 'docs')),
    test_suite="tests",
    scripts=['bin/gimme-aws-creds', 'bin/gimme-aws-creds.cmd', 'bin/gimme-aws-creds-autocomplete.sh'],
    classifiers=[
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: Apache Software License'
    ],
# This is probably the best way to install the CLI autocomplete script.  It would have autocomplete
# setup for all users on the host.  This is trying to copy the autocomplete script in the correct
# directory but sadly fails because only the root user can write in that directory:
#    data_files=[
#        ('/etc/bash_completion.d/', ['bin/gimme-aws-creds-completion.sh']),
#        ('/usr/local/etc/bash_completion.d/', ['bin/gimme-aws-creds-completion.sh'])
#    ]
# A fix is to override the installer class and add the execution of a post-install script that
# sources the autocomplete script in the user's profile:
    cmdclass={'install': gimme_aws_creds_installer}
)
