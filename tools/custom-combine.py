#!/usr/bin/env python
"""Simple script provides coverage combining across build chains."""
# pylint: disable=invalid-name
from __future__ import print_function

# local
import subprocess
import shutil
import glob
import os

# 3rd-party
import coverage
import six

PROJ_ROOT = os.path.join(os.path.dirname(__file__), os.pardir)
COVERAGERC = os.path.join(PROJ_ROOT, '.coveragerc')

def main():
    """Program entry point."""
    coverage_files = glob.glob(os.path.join(PROJ_ROOT, '._coverage.*'))
    for fname in coverage_files:
        dst_name = '.{0}'.format(os.path.basename(fname).lstrip('._'))
        dst_path = os.path.join(PROJ_ROOT, dst_name)
        try:
            shutil.copy(fname, dst_path)
        except:
            print('+ cp {0} {1}'.format(os.path.basename(fname), dst_name))
            raise
    cov = coverage.Coverage(config_file=COVERAGERC)
    cov.combine()
    cov.load()
    cov.html_report()
    print("--> open {0}/htmlcov/index.html for review."
          .format(os.path.relpath(PROJ_ROOT)))

    fout = six.StringIO()
    cov.report(file=fout)
    for line in fout.getvalue().decode('ascii').splitlines():
        if u'TOTAL' in line:
            total_line = line
            break
    else:
        raise ValueError("'TOTAL' summary not found in summary output")

    _, no_stmts, no_miss, _ = total_line.split(None, 3)
    no_covered = int(no_stmts) - int(no_miss)
    print("##teamcity[buildStatisticValue "
          "key='CodeCoverageAbsLTotal' "
          "value='{0}']".format(no_stmts))
    print("##teamcity[buildStatisticValue "
          "key='CodeCoverageAbsLCovered' "
          "value='{0}']".format(no_covered))

if __name__ == '__main__':
    main()
