#! /usr/bin/env python3
#
# Record aircraft that were seen during the day.
#
"""
Looks for aircraft & flights that were seen during a given day, and logs
them to the DB.
"""
import argparse
import PlaneReport as pr
import datetime
import time
from datetime import date, timedelta
#
# Print and/or log a list of flights/planes to DB
#
def buildRec(eventlist, dbconn, hex_or_flight, date):
    firstpl = eventlist[0]
    lastpl = eventlist[-1]
    if hex_or_flight == 'hex':
        daily_plane_seen = pr.DailyPlanesSeen(date_seen=date, hex=firstpl.hex,
                                              time_first_seen=firstpl.time,
                                              time_last_seen=lastpl.time,
                                              reporter=firstpl.reporter)
        return daily_plane_seen

    if hex_or_flight == 'flight':
        daily_flight_seen = pr.DailyFlightsSeen(date_seen=date, flight=firstpl.flight,
                                              time_first_seen=firstpl.time,
                                              time_last_seen=lastpl.time,
                                              reporter=firstpl.reporter)
        return daily_flight_seen

    return None
             
         
#
# Split a list on either flights or ICAO24 codes
#
def splitList(dbconn, start_time, end_time, hex_or_flight, date, debug, reporter,
              logToDB, printJSON, quiet, numRecs):
    orderSql = "order by %s, report_epoch" % hex_or_flight
    cur = pr.queryReportsDB(dbconn, myStartTime=start_time, myEndTime=end_time,
                         postSql=orderSql, printQuery=debug, myReporter=reporter)
    data = pr.readReportsDB(cur, numRecs)
    oldplane = None
    eventlist = []
    #
    # Split up into a separate list for each flight
    #
    while data:
        for plane in data:
            if not oldplane or getattr(oldplane, hex_or_flight) != getattr(plane, hex_or_flight):
                if oldplane:
                    pl = buildRec(eventlist, dbconn, hex_or_flight, date)
                    if not quiet:
                        if printJSON:
                            print(pl.to_JSON())
                        else:
                            first_ts = time.strftime("%Y-%m-%d %H:%M:%S",
                                                     time.localtime(pl.time_first_seen))
                            last_ts = time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.localtime(pl.time_last_seen))
                            print(getattr(pl, hex_or_flight), " seen between ", first_ts,
                                  " and ", last_ts)
                    if logToDB:
                        pl.logToDB(dbconn, debug)
                        dbconn.commit()
                eventlist = []
                eventlist.append(plane)
                oldplane = plane
            else:
                eventlist.append(plane)
        data = pr.readReportsDB(cur, numRecs)

    if eventlist:
        pl = buildRec(eventlist, dbconn, hex_or_flight, date)
        if not quiet:
            if printJSON:
                print(pl.to_JSON())
            else:
                first_ts = time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(pl.time_first_seen))
                last_ts = time.strftime("%Y-%m-%d %H:%M:%S",
                                        time.localtime(pl.time_last_seen))
                print(getattr(pl, hex_or_flight), " seen between ", first_ts,
                      " and ", last_ts)
        if logToDB:
            pl.logToDB(dbconn, debug)
            dbconn.commit()
 


parser = argparse.ArgumentParser(
    description="List the aircraft seen during the day")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-l', '--log-to-db', action="store_true", dest='logToDB', default=False,
                    help="Only list events, don't log them to the DBLog events to DB \
                    (default is to only print them out)")
parser.add_argument('-n', '--num-recs', dest='numRecs',
                    help="Number of records to read at a time(defaults to 100)", default=100)
parser.add_argument('-r', '--reporter', dest='reporter',
                    help="Name of the reporting data collector (defaults to Home1)",
                    default="Home1")
parser.add_argument('-j', '--json', action="store_true", dest='printJSON', default=False,
                    help="print events in JSON format (default is to print as text)")
parser.add_argument('-x', '--planes', action="store_true", dest='getPlanes', default=False,
                    help="Look for planes (denoted by their ICAO24 hex codes")
parser.add_argument('-f', '--flights', action="store_true", dest='getFlights', default=False,
                    help="Look for flights")
parser.add_argument('-d', '--date', dest='date', default=False,
                    help="The date we're interested in for the flights")
parser.add_argument('-q', '--quiet', action="store_true", dest='quiet', default=False,
                    help="Keep the noise to a minimum")

args = parser.parse_args()

if not args.db_conf:
    print("A valid URL db configuration file is needed!")
    exit(1)

if not args.date:
    print("A date is required!")
    exit(1)

if not (args.getFlights or args.getPlanes):
    print("At least one of --planes or --flights is required!")
    exit(1)

    
start_time = args.date + " 00:00:00"
end_time = args.date + " 23:59:59"

dbconn = pr.connDB(args.db_conf)

if args.getFlights:
    splitList(dbconn, start_time, end_time, 'flight', args.date, args.debug, args.reporter,
              args.logToDB, args.printJSON, args.quiet, args.numRecs)
if args.getPlanes:    
    splitList(dbconn, start_time, end_time, 'hex', args.date, args.debug, args.reporter,
              args.logToDB, args.printJSON, args.quiet, args.numRecs)

if args.logToDB:
    dbconn.commit()
    
