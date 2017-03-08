# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
  . /etc/bashrc
fi

# User specific aliases and functions
# set Dataverse API key, if valid key file (keyfile should contain only the API token
if [ -f "${HOME}/.dv-api-key" ]; then
  DV_API_KEY=$(cat "${HOME}/.dv-api-key" | grep -v "^\s*$" | grep -v "^\s*#" | tail -1)
  if [ -n "${DV_API_KEY}" ]; then
    export DV_API_KEY
  fi
fi
