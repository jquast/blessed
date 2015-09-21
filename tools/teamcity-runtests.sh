#!/bin/bash
set -e
set -o pipefail

here=$(cd `dirname $0`; pwd)
osrel=$(uname -s)

# run tests
cd $here/..

_cmd=tox
if [ X"$osrel" == X"Linux" ]; then
	# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=754248
	# cannot create a virtualenv for python2.6 due to use of
	# "{}".format in virtualenv, throws exception
	# ValueError: zero length field name in format.
	_cmd='tox -epy27,py33,py34,pypy,docs,sa'
fi

ret=0
echo ${_cmd}
${_cmd} || ret=$?

if [ $ret -ne 0 ]; then
	# we always exit 0, preferring instead the jUnit XML
	# results to be the dominate cause of a failed build.
	echo "py.test returned exit code ${ret}." >&2
	echo "the build should detect and report these failing tests." >&2
fi

# combine all coverage to single file, publish as build
# artifact in {pexpect_projdir}/build-output
mkdir -p build-output
coverage combine
mv .coverage build-output/.coverage.${osrel}.$RANDOM.$$
