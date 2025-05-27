#! /usr/bin/env python3
#
# Look for planes that might be taking off or landing at the airport.
# Need a fudge factor for altitude,
# as various aircraft seem to have the notion that the airport's
# altitude is up to 30 metres different
# from its official height. Bah.
#
"""
Attempts to determine and print out events (currently just takeoffs and landings)
from an airport.
"""
import argparse
import PlaneReport as pr 
import datetime
import time
from datetime import date, timedelta

#
# check to see if a given bearing is within a couple of degrees of another
#
def checkbearing(heading1, heading2, slop):
    if heading1  == heading2:
        return True
    lowercheck = False
    uppercheck = False
    
    lowerbound = heading1 - slop
    if lowerbound < 0:
        if heading2 >= 0 or heading2 >= (lowerbound + 360):
            lowercheck = True
    else:
        if heading2 >= lowerbound:
            lowercheck = True
    
    upperbound = heading1 + slop
    if upperbound >= 360:
        if heading2 <= (upperbound - 360):
            uppercheck = True
    else:
        if heading2 <= upperbound:
            uppercheck = True
        
    return uppercheck and lowercheck
    
#
# Look at list and determining if aircraft is ascending (taking off)
# or descending (landing)
# Print message accordinglys (or stuff it into a DB table)
#
def analyseList(eventlist, dbconn, airport, runway, logToDB=False, debug=False,
                printJSON=False, quiet=False):
    """
    Attempts to determine if event was a takeoff or landing

    Args:
        eventlist: A list of planereports ordered by time
        dbconn: a psycopg2 connection to a Postgres DB. Will be used to log
        events.
        logToDB: boolean to trigger logging events to a DB
        debug: Boolean for printing debug statements

    Returns:
        Nothing
    """
    firstplane = eventlist[0]
    lastplane = eventlist[-1]
    middleplane = eventlist[int(len(eventlist) / 2)]
    #
    # Are we actually using this runway, or are we crossing it?
    # Use runway heading and middleplane heading to find out.
    #
    
    otherheading = runway.heading - 180
    if otherheading < 0:
        otherheading += 360
    if not checkbearing(middleplane.track, runway.heading, 4) and not checkbearing(middleplane.track, otherheading, 4):
        return
    touchedgnd = False
    for plane in eventlist:
        if plane.isGnd:
            touchedgnd = True
    if firstplane.altitude >= lastplane.altitude: 
        event = "landed at"
    elif firstplane.altitude < lastplane.altitude:
        if touchedgnd:
            event = "bump & go at"
        else:
            event = "took off at"
    else:
        event = "dunno what to call this"

    airport_event = pr.AirportDailyEvents(airport=airport,
                                          event_time=lastplane.time,
                                          type_of_event=event[0],
                                          flight=lastplane.flight, hex=lastplane.hex,
                                          runway=runway.name)

    
    if not quiet:
        if printJSON:
            print(airport_event.to_JSON())
        else:
            print("Plane", lastplane.hex, "as flight", lastplane.flight, event,
                  time.strftime("%F %H:%M:%S", time.localtime(lastplane.time)),
                  "on runway", runway.name)


    if logToDB:
        airport_event.logToDB(dbconn, printQuery=debug)
        dbconn.commit()

#
# Look for various events for the plane in the airport
# (takeoffs or landings) A plane may visit an airport
# multiple times within a time period. Split the list
# up into multiple subevents and hand them off to be
# analysed.
#
MAX_SAME_ALT_CNT = 4
MIN_TURNAROUND_TIME = 600


def splitList(eventlist, dbconn, logToDB, debug, airport, runway, printJSON, quiet):
    """
    This function attempts to break up a list of planereports within an airport
    into separate lists that denote takeoff or landing events. Usually assessed
    by time gaps.

    Args:
        eventlist: A list of planereports ordered by time
        dbconn: a psycopg2 connection to a Postgres DB. Will be used to log
        events.
        logToDB: boolean to trigger logging events to a DB
        debug: Boolena for printing debug statements

    Returns:
        Nothing
    """
    tmplist = []
    oldplane = None

    for plane in eventlist:
        if not oldplane:
            oldplane = plane

        #
        # Check that the plane is not having another event
        # (assumes that turnaround time will be more than 20 minutes)
        # Will not pick up touch and go events
        #
        if (plane.time - oldplane.time) < MIN_TURNAROUND_TIME:

            tmplist.append(plane)
        else:
            if tmplist:
                analyseList(tmplist, dbconn, airport, runway, logToDB, debug, printJSON, quiet)
            tmplist = []
            tmplist.append(plane)

        oldplane = plane

    if tmplist:
        analyseList(tmplist, dbconn, airport, runway, logToDB, debug, printJSON, quiet)


parser = argparse.ArgumentParser(
    description="Locate those aircraft which may've landed or taken off from an airport ")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-t', '--start-time', dest='start_time',
                    help="The start of the time window from which records shall be retrieved, \
                    default 00:01 today")
parser.add_argument('-T', '--end-time', dest='end_time',
                    help="The end of the time window from which records shall be retrieved \
                    - default now")
parser.add_argument('-x', '--hex', dest='hexcodes',
                    help="The ICAO24 code(s) of the aircraft to be singled out, \
                    separated by commas when there are multiple instances")
parser.add_argument('-f', '--flights', dest='flights',
                    help="The flight numbers(s) of the aircraft to be singled out, \
                    separated by commas when there are multiple instances")
parser.add_argument('-A', '--airport', dest='airport',
                    help="The ICAO code for the airport we are interested in")
parser.add_argument('-a', '--committed-height', dest='committed_height',
                    help="The height above the airport below which the aircraft is \
                    considered to be interested in the airport(metres, default 200)", default=200)
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
parser.add_argument('-q', '--quiet', action="store_true", dest='quiet', default=False,
                    help="If chosen, don't print any output (default is false)")

parser.add_argument('--runway', dest='runways',
                    help="The names of the runways to be singled out, \
                    separated by commas when there are multiple instances", default=None)

args = parser.parse_args()

if not args.db_conf:
    print("A valid URL db configuration file is needed!")
    exit(1)

if not args.airport:
    print("An Airport is needed!")
    exit(1)
else:
    if not args.start_time:
        args.start_time = datetime.date.today().strftime("%F") + " 00:00:00"
    dbconn = pr.connDB(args.db_conf)
    reporter = pr.readReporter(dbconn, args.reporter, printQuery=args.debug)
    airport_list = pr.readAirport(dbconn, args.airport, printQuery=args.debug)
    for airport in airport_list:
        runways = pr.readRunways(dbconn, args.airport, printQuery=args.debug)
    
        for runway in runways:
            if args.debug:
                print(runway.to_JSON())
            if not args.runways or args.runways == runway.name:
                cur = pr.queryReportsDB(dbconn, myhex=args.hexcodes, myStartTime=args.start_time, \
                                        myEndTime=args.end_time, myflight=args.flights,
                                        maxAltitude=(int(args.committed_height) + airport.altitude),
                                        minAltitude=(airport.altitude - 150), myReporter=args.reporter,
                                        reporterLocation=reporter.location, printQuery=args.debug, \
                                        runways=runway.runway_area,
                                        postSql=" order by hex, report_epoch")
                data = pr.readReportsDB(cur, numRecs=10000)
                oldplane = None
                eventlist = []
                #
                # Split up into a separate list for each plane
                #
                while data:
                    for plane in data:
                        if args.debug:
                            print(plane.to_JSON())
                        if not oldplane:
                            eventlist.append(plane)
                        elif oldplane.hex == plane.hex:
                            eventlist.append(plane)
                        else:
                            splitList(
                                eventlist, dbconn, logToDB=args.logToDB, debug=args.debug,
                                airport=args.airport, runway=runway, printJSON=args.printJSON, quiet=args.quiet)
                            eventlist = []
                            eventlist.append(plane)
                        
                        oldplane = plane

                    data = pr.readReportsDB(cur, args.numRecs)

                    if eventlist:
                        splitList(eventlist, dbconn, logToDB=args.logToDB, debug=args.debug,
                                  airport=args.airport, runway=runway, printJSON=args.printJSON, quiet=args.quiet)

    if args.logToDB:
        dbconn.commit()
