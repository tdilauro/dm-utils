#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
DEFAULT_DIRS = ['.']
DEFAULT_FIELDS='tree, seq, depth, indicator, hash, size, filepath'

row_pattern = r'^(?P<prefix>[^"]*)?"(?P<filepath>.*?)"( -> "(?P<link_target>.*)")?(?P<indicator>[^"]*)$'
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
    p.add_argument('--no-tree-double-dash', dest='tree_double_dash', default=True, action='store_false',
                   help="set if your 'tree' command doesn't support '--' to end option flags")
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
    if args.tree_double_dash:
        tree_end_of_options = ['--']
    else:
        tree_end_of_options = []
    hash_alg = args.algorithm
    dirpaths = [os.path.abspath(p) for p in args.dirpaths]
    out_file_name = args.output

    fields = fields.replace(' ', '').split(',')
    headings = [f if f != 'hash' else hash_alg for f in fields]
    # options.append('--charset={}'.format(encoding))

    hash_class = getattr(hashlib, hash_alg)
    hasher = partial(checksum_file, hash_class=hash_class, chunk_size=64*1024)

    depth_by_separator = partial(get_depth, sep=sep_char)

    # generate the enhanced tree rows
    rows = tree_generator(command, options=options + tree_end_of_options, paths=dirpaths)
    rows = tree_line_parser(rows, depth_func=depth_by_separator, hasher=hasher)

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
    for path in paths:
        lines = subprocess_generator(command, options=options, paths=[path])
        for i, line in enumerate(lines):
            if i == 0:
                # the top-level directory does not include an indicator, so we'll add one before yielding
                yield 'trunk', line + '/'
            else:
                yield 'branch', line


def subprocess_generator(command, options=None, paths=None):
    if options is None:
        options = []
    if paths is None:
        paths = []
    p = subprocess.Popen([command] + options + paths,
                         stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
    while True:
        line = p.stdout.readline()
        if line != '':
            yield line
        else:
            break
    p.stdout.close()


valid_fields = ['seq', 'depth', 'row', 'tree', 'branches', 'filepath', 'filename', 'indicator', 'hash', 'size']
def tree_line_parser(typed_rows, fields=None, valid_fields=valid_fields, depth_func=None, hasher=None, encoding='utf-8'):
    for seq, typed_row in enumerate(typed_rows):
        type, row = typed_row
        m = row_cp.match(row)
        branches = m.groupdict()['prefix']
        filepath = m.groupdict()['filepath']
        os_filepath = filepath.encode('utf-8').decode('unicode_escape')
        os_filestats = os.stat(os_filepath)
        filename = os.path.basename(filepath)
        indicator = m.groupdict()['indicator']
        if type == 'trunk':
            rel_depth = depth_func(filepath)
        depth = depth_func(filepath, start=rel_depth)
        if indicator is not None:
            indicator = ls_indicators[indicator.strip()]
        tree = branches + filename
        size = os_filestats.st_size

        # hashes only for regular files
        if stat.S_ISREG(os_filestats.st_mode):
            hash = hasher(os_filepath)
        else:
            hash = ''

        properties = property_dict(locals(), valid_fields)
        yield properties


def property_dict(variables, fields):
    return dict(((k, variables[k]) for k in fields))


def get_depth(path, sep=b'/', start=0):
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
    try:
        main()
    except KeyboardInterrupt:
        pass
    except BrokenPipeError as e:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)
