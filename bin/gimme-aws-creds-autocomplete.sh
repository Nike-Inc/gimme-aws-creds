#/usr/bin/env bash
#
# Auto-complete script for gimme-aws-creds.
#
# Links:
#   https://www.gnu.org/software/bash/manual/html_node/Programmable-Completion-Builtins.html#Programmable-Completion-Builtins
#
# To use in your current shell:
#   /> source gimme-aws-creds-completion.sh
#
# To auto-load in new shells, copy to the system wide bash completion directory:
#   on Mac: /usr/local/etc/bash_completion.d/
#   on Linux: /etc/bash_completion.d/
#   on Windows: who cares???
#

gimme-aws-creds_autocomplete()
{
  local _cmd_line="${COMP_LINE}"
  local _cur="${COMP_WORDS[COMP_CWORD]}"
  local _prev="${COMP_WORDS[COMP_CWORD-1]}"
  local _opts="--help --action-configure --configure --output-format --profile --resolve --insecure -keep --version --action-list-profiles --list-profiles --action-list-roles --open-browser"
  local _suggestions=""
  if [[ "${_prev}" == "gimme-aws-creds" && "${_cur}" == "" ]] ; then
    _suggestions=($(compgen -W "${_opts}" "${_cur}"))
  elif [[ "${_cur}" == "-" ]] ; then
    _suggestions=($(compgen -W "${_opts}" "${_cur}"))
  elif [[ "${_cur}" =~ "--" ]] ; then
    _suggestions=($(compgen -W "${_opts}" -- "${_cur}"))
  elif [ "${_prev}" == "--profile" ] || [ "${_prev}" == "-p" ] ; then
    # Get a list of profiles from the okta config-file (if we have some):
    local IFS=$'\n'
    local _creds_cfg_file=${HOME}/.okta_aws_login_config
    if [ -f ${_creds_cfg_file} ] ; then
      local _profiles=$(grep "^\[" ${_creds_cfg_file} | sed -e 's/\[//' -e 's/\]//')
      [ ! -z "${_profiles}" ] && _suggestions=($(compgen -W "${_profiles}" "${_cur}"))
    fi
  elif [ "${_prev}" == "--output-format" ] || [ "${_prev}" == "-o" ] ; then
    _suggestions=($(compgen -W "export json" "${_cur}"))
  fi
  COMPREPLY=("${_suggestions[@]}")
}

complete -F gimme-aws-creds_autocomplete gimme-aws-creds
