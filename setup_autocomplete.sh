#!/usr/bin/env bash
#----------------------------------------------------#
# Gimme-aws-creds post-installation script.
# This script adds the CLI autocomplete to your shell's environment.
#----------------------------------------------------#
INSTALL_DIR=$(dirname $(which gimme-aws-creds))

if [ "$(basename $SHELL)" = "bash" ] && [ -f ~/.bashrc ] ; then
  grep -q 'gimme-aws-creds-autocomplete' ~/.bashrc
  if [[ $? -ne 0 ]] ; then
    echo "Adding autocomplete setup to ~/.bashrc"
    echo "Source in .bashrc or simply restart your shell."
    echo "" >> ~/.bashrc
    echo "# Loading gimme-aws-creds CLI autocomplete:" >> ~/.bashrc
    echo "source ${INSTALL_DIR}/gimme-aws-creds-autocomplete.sh" >> ~/.bashrc
  fi
elif [ "$(basename $SHELL)" = "zsh" ] && [ -f ~/.zshrc ] ; then
  grep -q 'gimme-aws-creds-autocompletion' ~/.zshrc
  if [[ $? -ne 0 ]] ; then
    echo "Adding autocomplete setup to ~/.zshrc"
    echo "Source in .zshrc or simply restart your shell."
    echo "" >> ~/.zshrc
    echo "# Loading gimme-aws-creds CLI autocomplete:" >> ~/.zshrc
    echo "autoload bashcompinit" >> ~/.zshrc
    echo "bashcompinit" >> ~/.zshrc
    echo "source ${INSTALL_DIR}/gimme-aws-creds-autocomplete.sh" >> ~/.zshrc
  fi
else
  echo "Not sure how to install this in your shell: $(basename $SHELL)"
fi