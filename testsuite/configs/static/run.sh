#!/bin/bash
#
# Run static code checks
# 
# 
# The first argument it the root directory of our repository

# Should this stuff be configurable?

# Root directory is either $1 (first argument, ${WORKSPACE} environment
# variable, or, as a last resort pwd ('.')
#
# This directory should contain the cerebrum repository, and serves as our
# working directory.
crb_src=${1:-${WORKSPACE:-'.'}}

# Source the setup functions
if ! source ${crb_src}/testsuite/scripts/setup_tools.sh
then
    echo " ** FATAL: Unable to load script tools from '${crb_src}'" >&2
    exit 1
fi

# If the above succeeds, this should be redundant
if ! [ -d "${crb_src}/Cerebrum" ]
then
    error "Working dir '${crb_src}' does not contain the cerebrum source code"
    exit 1
fi

# Config dir.
# It's the directory we're working from, i.e. the dirname of this script. This
# directory should contain configs for our test tools
config=$( abs_dirname "${BASH_SOURCE[0]}" )


#
# We need a virtualenv prefix to install test tools into
#
tools="${crb_src}/tools_env"
if [ ! -f "${tools}/bin/activate" ]
then
    info "Setting up new virtualenv in '${tools}'"
    virtualenv ${tools}
    assert_retval virtualenv "Unable to set up virtualenv prefix '${tools}'"
fi

# Our binaries
export CRB_PY=${tools}/bin/python
export CRB_PIP=${tools}/bin/pip

# If the folder ${HOME}/pypi exists, we expect to find all the relevant packages
# there, and we'll install packages in 'offline mode' (pip --no-index)
if [ -d "${HOME}/pypi" ]
then
    pip_cache="${HOME}/pypi"
    offline="true"
else
    pip_cache="${tools}/pip_cache"
fi

pip_install_reqs "${config}/pip.txt" "${pip_cache}" $offline
assert_retval pip_install_reqs "Unable to install packages"

# Setup pythonpath for the tests
#
export PYTHONPATH=$( prepare_pypath ${crb_src} )
assert_retval prepare_pypath

## Setup DONE. Ready to begin static checks

#
# Run pep8 syntax check
# 
info "Running static test: pep8"
${tools}/bin/pep8 --format=default --exclude=extlib \
                    ${crb_src}/Cerebrum ${crb_src}/contrib > ${crb_src}/pep8.txt

# 
# Run pylint error checks
#
info "Running static test: pylint"

#pylint_init="f='${env_dir}/bin/activate_this.py';execfile(f, dict(__file__=f))"

# Note that we ignore E1101(no-member), as pylint won't recognize mixins that
# aren't named '*mixin'. Maybe we should solve this better by setting
# 'ignored-classes' in pylintrc? Not entirely sure what effect that has, but
# it's recommended to do that for 'classes with dynamically set attributes'
${tools}/bin/pylint --rcfile=${config}/pylintrc Cerebrum > ${crb_src}/pylint.txt

# Contrib and other python files outside Cerebrum are not in our path. They need
# to be checked individually. Let's do just that, and append to the pylint
# report
for f in $( find ${crb_src}/contrib -name *.py )
do
    ${tools}/bin/pylint --rcfile=${config}/pylintrc $f >> ${crb_src}/pylint.txt
done

# If reached, all tests completed and the test is, in essence, successful.
#
true
