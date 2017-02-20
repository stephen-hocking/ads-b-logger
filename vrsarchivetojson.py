#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr


parser = argparse.ArgumentParser(
    description="Read a bunch of VRS archive files (from unzipped daily archive) and convert them to our JSON format")
parser.add_argument('filenames', metavar='N', nargs='+',
                    help="A list of filenames to be opened")

args = parser.parse_args()

if not args.filenames:
    print("One or more files are needed!")
    exit(-1)

for fn in args.filenames:
    fh = pr.openFile(fn)
    pos_reports = pr.readVRSFromFile(fh)
    for pl in pos_reports:
        print(pl.to_JSON())
    fh.close()
