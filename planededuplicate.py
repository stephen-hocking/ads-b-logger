#! /usr/bin/env python3
#
#
# This program removes duplicate (except the timestamp position reports from the database.
# The duplicates arise because aircraft normat only broadcast a position message every few seconds,
# but will update their postion whenever they're queried by the ATC, which can be at least once
# a second when they're nearing an airport. Away from the ATC, they will still be sending other
# message types, which means that dump1090 will be tagging them as seen within a small sample period,
# so if we're sampling dump1090 every second, we will get quite a few duplicate reports. This program
# attempts to weed those duplicates out.
#
import argparse
import PlaneReport as pr
import datetime
from datetime import date, timedelta


def comparePlanes(oldplane, plane):
    if not oldplane:
        return 8
    if oldplane.hex != plane.hex:
        return 1
    if oldplane.flight != plane.flight:
        return 2
    if oldplane.report_location != plane.report_location:
        return 3
    if (plane.time - oldplane.time) > 10:
        return 9
#    if oldplane.track != plane.track:
#        return 4
#    if oldplane.speed != plane.speed:
#        return 5
#    if oldplane.vert_rate != plane.vert_rate:
#        return 6
#    if oldplane.altitude != plane.altitude:
#        return 7
    else:
        return 0

reasons = {
    0: "is equal",
    1: "hex value",
    2: "flight value",
    3: "location value",
    4: "track value",
    5: "speed value",
    6: "vert_rate value",
    7: "altitude value",
    8: "null oldplane",
    9: "too long in one spot"
}

recorded_reasons = [x for x in range(0, 10)]

for i in range(0, 10):
    recorded_reasons[i] = 0

parser = argparse.ArgumentParser(
    description="Get rid of duplicate plane position reports.")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-l', '--list-only', action="store_true", dest='list',
                    default=False, help="Only list the duplicates, do not delete")
parser.add_argument('-t', '--start-time', dest='start_time',
                    help="The start of the time window from which records shall be retrieved, default 00:01 today")
parser.add_argument('-T', '--end-time', dest='end_time',
                    help="The end of the time window from which records shall be retrieved - default now")
parser.add_argument('-x', '--hex', dest='hexcodes',
                    help="The ICAO24 code(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-f', '--flights', dest='flights',
                    help="The flight numbers(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-d', '--min-distance', dest='minDistance',
                    help="Minimum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres",
                    type=float)
parser.add_argument('-D', '--max-distance', dest='maxDistance',
                    help="Maximum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres",
                    type=float)
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
    exit(-1)
else:
    yesterday = datetime.date.today() - timedelta(1)
    if not args.start_time:
        args.start_time = yesterday.strftime("%F") + " 00:00:00"
    if not args.end_time:
        args.end_time = yesterday.strftime("%F") + " 23:59:59"
    dbconn = pr.connDB(args.db_conf)
    oldplane = None
    reporter = pr.readReporter(dbconn, args.reporter)
    delete_count = 0
    this_plane_delete = 0
    delete_list = []
    cur = pr.queryReportsDB(dbconn, myhex=args.hexcodes, myStartTime=args.start_time, myEndTime=args.end_time, myflight=args.flights, minDistance=args.minDistance, maxDistance=args.maxDistance,
                            minAltitude=args.minAltitude, maxAltitude=args.maxAltitude, myReporter=args.reporter, reporterLocation=reporter.location, printQuery=args.debug, postSql=" order by hex, report_epoch, report_location")
    data = pr.readReportsDB(cur, args.numRecs)
    while data:
        for plane in data:

            notequal = comparePlanes(oldplane, plane)

            if not notequal:
                if args.debug or args.list:
                    print("Deleting " + plane.to_JSON())
                    print(oldplane.to_JSON())
                if not args.list:
                    delete_list.append(plane)
                delete_count += 1
                this_plane_delete += 1
            else:
                if this_plane_delete:
                    this_plane_delete = 0
                    if args.list or args.debug:
                        print("Plane ", oldplane.to_JSON(), " had ",
                              str(this_plane_delete), " duplicates")
                        print(
                            "Different plane ", reasons[notequal], " ", plane.to_JSON())
                recorded_reasons[notequal] += 1

                oldplane = plane
                if args.debug:
                    print("New record " + plane.to_JSON())
        for plane in delete_list:
            plane.delFromDB(dbconn, args.debug)
        dbconn.commit()
        delete_list = []

        data = pr.readReportsDB(cur, args.numRecs)
    print("Deleted records", delete_count)
    if args.debug:
        for i in range(0, len(reasons)):
            print(reasons[i], " ", recorded_reasons[i])
