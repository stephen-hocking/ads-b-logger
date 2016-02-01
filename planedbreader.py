#! /usr/bin/env python3
#
#
import argparse
import PlaneReport as pr
import datetime
from datetime import date, timedelta

parser = argparse.ArgumentParser(
    description="Extract previously recorded plane position reports from DB, to stdout ")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-t', '--start-time', dest='start_time',
                    help="The start of the time window from which records shall be retrieved, default 00:01 today")
parser.add_argument('-T', '--end-time', dest='end_time',
                    help="The end of the time window from which records shall be retrieved - default now")
parser.add_argument('-x', '--hex', dest='hexcodes',
                    help="The ICAO24 code(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-f', '--flights', dest='flights',
                    help="The flight numbers(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-d', '--min-distance', dest='minDistance',
                    help="Minimum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres")
parser.add_argument('-D', '--max-distance', dest='maxDistance',
                    help="Maximum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres")
parser.add_argument('-A', '--max-altitude', dest='maxAltitude',
                    help="The aircraft has to be at an altitude lower than this (Units are in metres)", type=float)
parser.add_argument('-a', '--min-altitude', dest='minAltitude',
                    help="The aircraft has to be at an altitude higher than this (Units are in metres)", type=float)
parser.add_argument('-n', '--num-recs', dest='numRecs',
                    help="Number of records to read at a time(defaults to 100)", default=100, type=int)
parser.add_argument('-r', '--reporter', dest='reporter',
                    help="Name of the reporting data collector (defaults to Home1)", default="Home1")


args = parser.parse_args()

if not args.db_conf:
    print("A valid URL db configuration file is needed!")
    exit(1)
else:
    if not args.start_time:
        args.start_time = datetime.date.today().strftime("%F") + " 00:00:00"
    dbconn = pr.connDB(args.db_conf)
    reporter = pr.readReporter(dbconn, args.reporter)
    cur = pr.queryReportsDB(dbconn, myhex=args.hexcodes, myStartTime=args.start_time, myEndTime=args.end_time, myflight=args.flights, minDistance=args.minDistance, maxDistance=args.maxDistance,
                            minAltitude=args.minAltitude, maxAltitude=args.maxAltitude, myReporter=args.reporter, reporterLocation=reporter.location, printQuery=args.debug, postSql=" order by report_timestamp")
    data = pr.readReportsDB(cur)
    while data:
        for plane in data:
            print(plane.to_JSON())
        data = pr.readReportsDB(cur, args.numRecs)
