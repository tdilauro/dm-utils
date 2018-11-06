#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import filecmp
from functools import partial
import os
import subprocess
import sys
import shutil
import re

"""
Author: Tim DiLauro <timmo@jhu.edu>

tree -fFQ "$PWD"
"/Users/timmo/src/git/dm-utils"
├── "/Users/timmo/src/git/dm-utils/Pipfile"
├── "/Users/timmo/src/git/dm-utils/Pipfile.lock"
├── "/Users/timmo/src/git/dm-utils/README.md"
├── "/Users/timmo/src/git/dm-utils/bin"/
│   ├── "/Users/timmo/src/git/dm-utils/bin/altbag"*
│   ├── "/Users/timmo/src/git/dm-utils/bin/aspace-sql-dump.sh"*
│   ├── "/Users/timmo/src/git/dm-utils/bin/dv-api-settings"*
│   ├── "/Users/timmo/src/git/dm-utils/bin/dv-sw-upload"*
│   ├── "/Users/timmo/src/git/dm-utils/bin/dv-sword-upload"*
│   └── "/Users/timmo/src/git/dm-utils/bin/zipcheck"*
├── "/Users/timmo/src/git/dm-utils/supertree.py"
├── "/Users/timmo/src/git/dm-utils/tree_date_histogram"*
└── "/Users/timmo/src/git/dm-utils/tree_date_range"*
"""

COMMAND = 'tree'
TREE_ARGS = "-afFQ"

row_pattern = r'^(?P<prefix>.*)?"(?P<filepath>.*)"(?P<suffix>[^"]*)$'
row_cp = re.compile(row_pattern)


def main():
    command = COMMAND
    options = TREE_ARGS

    sep_char = os.path.sep

    with subprocess.Popen([command, options, '--noreport'], stdout=subprocess.PIPE) as p:
        out = p.communicate()[0].splitlines(False)
        basedir = out.pop(0).decode('utf-8')
        # configure function partial based on basedir
        depth_from_base = partial(get_depth, sep=sep_char, start=basedir.count(sep_char))

        for i, row in enumerate(out, 1):
            row = row.decode('utf-8')
            m = row_cp.match(row)
            filepath = m.groupdict()['filepath']
            depth = depth_from_base(filepath)
            filetype = m.groupdict()['suffix']
            filestats = os.stat()
            print(i, depth, filetype, row)


def get_depth(path, sep='/', start='0'):
    return path.count(sep) -  start


if __name__=='__main__':
    main()
