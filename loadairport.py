#! /usr/bin/env python3
#
#
import argparse
import PlaneReport as pr

print("Deprecated! - Do not use!")
exit(1)

parser = argparse.ArgumentParser(
    description="Load an airport into the DB from a simple text file")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('-u', '--update', action="store_true", dest='update',
                    default=False, help="Update the airport data, rather than create it")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to populate a database (only makes sense when a DB Conf file is specified)")

args = parser.parse_args()

if not args.db_conf:
    print("A valid URL db configuration file is needed!")
    exit(1)

if not args.datafile:
    print("A valid airport file is needed!")
    exit(1)

dbconn = pr.connDB(args.db_conf)
inputfile = pr.openFile(args.datafile)

airport = pr.readAirportFromFile(inputfile)

airport.logToDB(dbconn, update=args.update, printQuery=args.debug)
dbconn.commit()

if args.debug:
    print(airport.to_JSON())
