#! /usr/bin/env python3
#
#
# Load a reporter into the DB
# from a 4 line text file.
import argparse
import PlaneReport as pr

def readReporterFromFile(inputfile):
    """
    Read Reporter  from a handbuilt text file

    Args:
        inputfile: Pathname of file

    Returns:
        An Reporter object

        Very basic - no error checking whatsoever! File format is:
            Line 1: Name of reporter (no more than 10 chars)
            Line 2: reporter type piaware or mutability, although this field isn't used by anything yet
            Line 3: Lat/lon of reporter location, comma separated.
            Line 4: URL to access the reporter, e.g. http://planereporter/dump1090/data/aircraft.json

    """
    reporter = {}
    name = inputfile.readline().strip('\n')
    mytype = inputfile.readline().strip('\n')
    coords = inputfile.readline().split(",")
    lat = float(coords[0].strip())
    lon = float(coords[1].strip())
    url = inputfile.readline().strip('\n')
    reporter = pr.Reporter(name=name, mytype=mytype, lat=lat, lon=lon,
                           url=url, location="")

    return reporter

parser = argparse.ArgumentParser(
    description="Load an report into the DB from a simple text file")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('-u', '--update', action="store_true", dest='update',
                    default=False, help="Update the reporter data, rather than create it")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-f', '--file', dest='datafile',
                    help="The file to load the reporter data from")
parser.add_argument('-l', '--log-to-db', dest='logToDB', action="store_true",
                    default=False, help="Log the data to the DB")


args = parser.parse_args()

dbconn = False

if not args.db_conf and (args.logToDB or args.update):
    print("A valid URL db configuration file is needed to log data to the database!")
    exit(1)

if not args.datafile:
    print("A valid reporter file is needed!")
    exit(1)

if args.db_conf:
    dbconn = pr.connDB(args.db_conf)

inputfile = pr.openFile(args.datafile)

reporter = readReporterFromFile(inputfile)

if args.logToDB or args.update:
    reporter.logToDB(dbconn, update=args.update, printQuery=args.debug)
    dbconn.commit()

if args.debug:
    print(reporter.to_JSON())
