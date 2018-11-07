#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import argparse
import unicodecsv as csv
from functools import partial
import hashlib
import os
import re
import subprocess
import stat
import sys

DEFAULT_CHARSET = 'utf-8'
DEFAULT_HASH = 'md5'
DEFAULT_COMMAND = 'tree'
DEFAULT_TREE_ARGS = ['-afFSQ', '--noreport']
# comma-separated list of directories
DEFAULT_DIRS = '.'
DEFAULT_FIELDS='tree, seq, depth, filepath, hash, size'

row_pattern = r'^(?P<prefix>.*)?"(?P<filepath>.*)"(?P<suffix>[^"]*)$'
row_cp = re.compile(row_pattern)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--alg', dest='algorithm', default=DEFAULT_HASH, help='checksum algorithm')
    p.add_argument('-o', '--output', dest='output', default='-', help='output filename (default: "-" (STDOUT)')
    p.add_argument('dirpaths', nargs='*', default=DEFAULT_DIRS,
                   help="comma-separated list of directories (default is current directory")
    args = p.parse_args()

    # parameters from defaults
    charset = DEFAULT_CHARSET
    sep_char = os.path.sep
    fields = DEFAULT_FIELDS
    command = DEFAULT_COMMAND
    options = DEFAULT_TREE_ARGS

    # params from arguments
    hash_alg = args.algorithm
    dirpaths = args.dirpaths.replace(' ', '').split(',')
    dirpaths = [os.path.abspath(p) for p in dirpaths]
    outfile = args.output

    fields = fields.replace(' ', '').split(',')
    options.append('--charset={}'.format(charset))

    if outfile == '-':
        # stdout - sending bytes different between Py2 and Py3
        try:
            outfile = sys.stdout.buffer
        except AttributeError:
            outfile = sys.stdout
    else:
        outfile = open(outfile, mode='wb')

    hash_class = getattr(hashlib, hash_alg)
    hasher = partial(checksum_file, hash_class=hash_class, chunk_size=64*1024)


    p = subprocess.Popen([command] + options + ['--'] + dirpaths, stdout=subprocess.PIPE)
    out = p.communicate()[0].splitlines(False)
    p.stdout.close()

    basedir = out[0].decode(charset)
    # configure function partial based on basedir
    depth_from_base = partial(get_depth, sep=sep_char, start=basedir.count(sep_char))

    rows = tree_lines(out, depth_func=depth_from_base, hasher=hasher)
    emit_csv(rows, fields=fields, fileobj=outfile, encoding=charset)


def tree_lines(out, fields=None, depth_func=None, hasher=None, encoding='utf-8'):
    valid_fields = ['seq', 'depth', 'row', 'tree', 'branches', 'filepath', 'filename', 'hash', 'size']
    for seq, row in enumerate(out, 1):
        row = row.decode(encoding)
        m = row_cp.match(row)
        branches = m.groupdict()['prefix']
        filepath = m.groupdict()['filepath']
        filename = os.path.basename(filepath)
        depth = depth_func(filepath)
        filetype = m.groupdict()['suffix']
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


def emit_csv(rows, fields=None, fileobj=None, encoding='utf-8'):
    with fileobj as csvfile:
        if fields is None:
            return
        writer = csv.DictWriter(csvfile, encoding=encoding, fieldnames=fields, restval='', extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__=='__main__':
    main()
