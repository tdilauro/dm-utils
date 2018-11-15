#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import argparse
import unicodecsv as csv
from functools import partial
import hashlib
import os
import re
import shutil
import subprocess
import stat
import sys
import tempfile

DEFAULT_CHARSET = 'utf-8'
DEFAULT_HASH = 'md5'
DEFAULT_COMMAND = 'tree'
DEFAULT_TREE_ARGS = ['-fFQ', '--noreport', '--charset=ASCII']
# comma-separated list of directories
DEFAULT_DIRS = '.'
DEFAULT_FIELDS='tree, seq, depth, indicator, filepath, hash, size'

row_pattern = r'^(?P<prefix>.*)?"(?P<filepath>.*)"(?P<indicator>[^"]*)$'
row_cp = re.compile(row_pattern)

# indicators from 'tree -F' or 'ls -F'
"""
ls_indicators = {
    '@': 'symlink/xattrs',
    '*': 'executable',
    '=': 'socket',
    '|': 'named pipe',
    '>': 'door',
    '/': 'directory',
    '': 'file',
}
"""
# '*' really indicates 'executable', but 'file' is good for our purposes at the moment
ls_indicators = {
    '@': 'symlink/xattrs',
    '*': 'file',
    '=': 'socket',
    '|': 'named pipe',
    '>': 'door',
    '/': 'directory',
    '': 'file',
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--alg', dest='algorithm', default=DEFAULT_HASH, help='checksum algorithm')
    p.add_argument('-a', '--all', dest='all_files', action='store_true', default=False,
                   help='include hidden files and directories')
    p.add_argument('-o', '--output', dest='output', default='-', help='output filename (default: "-" (STDOUT)')
    p.add_argument('dirpaths', nargs='*', default=DEFAULT_DIRS,
                   help="list of directories (default is current directory")
    args = p.parse_args()

    # parameters from defaults
    encoding = DEFAULT_CHARSET
    sep_char = os.path.sep
    fields = DEFAULT_FIELDS
    command = DEFAULT_COMMAND
    options = DEFAULT_TREE_ARGS

    # params from arguments
    if args.all_files:
        options.append('-a')
    hash_alg = args.algorithm
    dirpaths = [os.path.abspath(p) for p in args.dirpaths]
    out_file_name = args.output

    fields = fields.replace(' ', '').split(',')
    headings = [f if f != 'hash' else hash_alg for f in fields]
    # options.append('--charset={}'.format(encoding))

    hash_class = getattr(hashlib, hash_alg)
    hasher = partial(checksum_file, hash_class=hash_class, chunk_size=64*1024)

    rows = tree_generator(command, options=options, paths=dirpaths)
    # first result from tree_generator() contains the base directory
    basedir = next(rows)
    # configure function partial based on basedir
    depth_from_base = partial(get_depth, sep=sep_char, start=basedir.count(sep_char))

    # generate the enhanced tree rows
    rows = tree_lines(rows, depth_func=depth_from_base, hasher=hasher)

    # stdout - sending bytes different between Py2 and Py3
    try:
        stdout = sys.stdout.buffer
    except AttributeError:
        stdout = sys.stdout

    if out_file_name == '-':
        outfile = stdout
    else:
        # use tempfile in same directory as target output file, so we can rename in place
        dirname, basename = os.path.split(out_file_name)
        outfile= tempfile.NamedTemporaryFile(prefix='{}.tmp-'.format(basename), dir=dirname, delete=False)

    emit_csv(rows, fields=fields, headings=headings, csvfile=outfile, encoding=encoding)

    # don't close or rename stdout! only a file!
    if out_file_name != '-':
        outfile.close()
        shutil.move(outfile.name, out_file_name)


def tree_generator(command, options=None, paths=None):
    lines = subprocess_generator(command, options=options, paths=paths)
    # py2/py3 compatibility, so can't use 'yield from'
    for i, line in enumerate(lines):
        if i == 0:
            # the first value yielded is for calculating relative filesystem depth
            yield line
            # the top-level directory does not include an indicator, so we'll add one before yielding
            line = line + '/'
        # yield all the rows in the hierarchy
        yield line


def subprocess_generator(command, options=None, paths=None):
    if options is None:
        options = []
    if paths is None:
        paths = []
    p = subprocess.Popen([command] + options + ['--'] + paths,
                         stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
    while True:
        line = p.stdout.readline()
        if line != '':
            yield line
        else:
            break
    p.stdout.close()


valid_fields = ['seq', 'depth', 'row', 'tree', 'branches', 'filepath', 'filename', 'indicator', 'hash', 'size']
def tree_lines(rows, fields=None, valid_fields=valid_fields, depth_func=None, hasher=None, encoding='utf-8'):
    for seq, row in enumerate(rows, 0):
        m = row_cp.match(row)
        branches = m.groupdict()['prefix']
        filepath = m.groupdict()['filepath']
        filename = os.path.basename(filepath)
        depth = depth_func(filepath)
        indicator = m.groupdict()['indicator']
        if indicator is not None:
            indicator = ls_indicators[indicator.strip()]
        tree = branches + filename
        filestats = os.stat(filepath)

        # hashes and sizes only for regular files
        if stat.S_ISREG(filestats.st_mode):
            hash = hasher(filepath)
            size = filestats.st_size
        else:
            hash = ''
            size = 0

        properties = property_dict(locals(), valid_fields)
        yield properties


def property_dict(variables, fields):
    return dict(((k, variables[k]) for k in fields))


def get_depth(path, sep=b'/', start='0'):
    return path.count(sep) -  start


def checksum_file(fname, hash_class=None, chunk_size=4*1024):
    checksummer = hash_class()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            checksummer.update(chunk)
    return checksummer.hexdigest()


def emit_csv(rows, fields=None, headings=None, csvfile=None, encoding='utf-8'):
    if fields is None:
        return
    if headings is None:
        headings = fields
    writer = csv.DictWriter(csvfile, encoding=encoding, fieldnames=fields, restval='', extrasaction='ignore')
    # use the underlying writer, so we can write our own headings
    writer.writer.writerow(headings)
    for row in rows:
        writer.writerow(row)


if __name__=='__main__':
    main()
