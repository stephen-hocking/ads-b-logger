#! /usr/bin/env python3
#
#
import time
import requests
import argparse
import PlaneReport as pr

#
# Set timestamp to initial nonsense value (is secs since epoch)
# Code may break in 2038 (Hey! I is a poet!)
#
sample_timestamp = 0


parser = argparse.ArgumentParser(
    description="load DB from backed up daily records")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('-n',  dest='numrecs',  default=100, type=int,
                    help="Number of records to process at once")
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to populate a database (only makes sense when a DB Conf file is specified)")


args = parser.parse_args()

reporter = None
dbconn = None

if not args.db_conf or not args.datafile:
    print("A valid filename and db connection is needed!")
    exit(-1)

if args.db_conf:
    dbconn = pr.connDB(args.db_conf)
    inputfile = pr.openFile(args.datafile)
    data = pr.readFromFile(inputfile, numRecs=args.numrecs)
    while data:
        for plane in data:
    #        if not plane.reporter:
    #            plane.reporter = args.reporter
            if dbconn:
                plane.logToDB(dbconn, printQuery=args.debug)
            else:
                print(plane.to_JSON())
        if dbconn:
            dbconn.commit()
        data = pr.readFromFile(inputfile, numRecs=args.numrecs)
