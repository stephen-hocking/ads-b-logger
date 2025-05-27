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
    description="Acquire plane position reports from dump1090 and log them, to stdout or a DB")
parser.add_argument('-i', '--sample-interval', type=int, dest='boredom_threshold',
                    help="Number of seconds between each sample - default is 1", default=1)
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-c', '--sample-count', type=int, dest='num_samps',
                    help="Number of samples to collect (-1 for infinity) - default is 1", default=1)
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('-u', '--url', dest='dump1090url',
                    help="A URL presented by a machine running dump1090, e.g. http://somebox:8080/data.json")
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to populate a database (only makes sense when a DB Conf file is specified)")
parser.add_argument('-d', '--min-distance', dest='minDistance',
                    help="Minimum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres",
                    default=0.0, type=float)
parser.add_argument('-D', '--max-distance', dest='maxDistance',
                    help="Maximum distance that the aircraft can be from a specified reporting point (which defaults to Home1). Units are in metres",
                    default=450000.0, type=float)
parser.add_argument('-A', '--max-altitude', dest='maxAltitude',
                    help="The aircraft has to be at an altitude lower than this (Units are in metres, default 20000)",
                    default=20000, type=float)
parser.add_argument('-a', '--min-altitude', dest='minAltitude',
                    help="The aircraft has to be at an altitude higher than this (Units are in metres default is 0)",
                    default=0, type=float)
parser.add_argument('-S', '--max-speed', dest='maxSpeed',
                    help="The aircraft has to be at a speed lower than this (Units are in km/h)", default=3500.0, type=float)
parser.add_argument('-s', '--min-speed', dest='minSpeed',
                    help="The aircraft has to be at a speed greater than this (Units are in km/h)", default=0.0, type=float)
parser.add_argument('-r', '--reporter', dest='reporter',
                    help="The name of the reporting device - defaults to Home1", default="Home1")
parser.add_argument('--lat', dest='lat',
                    help="Latitude of the centre of the area we are interested in", type=float)
parser.add_argument('--lon', dest='lon',
                    help="Longitude of the centre of the area we are interested in", type=float)

parser.add_argument('-v', '--vrs-fmt', action='store_true', dest='vrs_fmt',
                    help="URL refers to VRS adsbexchange.com", default=False)


parser.add_argument('-t', '--timeout', dest='mytimeout', type=float,
                    help="Amount of time to wait before cancelling calls to URL", default=0.5)


parser.add_argument('-n', '--numrecs', dest='numrecs', type=int,
                    help="Number of records to read at a time", default=100)




args = parser.parse_args()

reporter = None
dbconn = None

if not args.dump1090url and not args.db_conf and not args.datafile:
    print("A valid URL or a valid filename or db connection is needed!")
    exit(-1)

if args.db_conf:
    dbconn = pr.connDB(args.db_conf)
    reporter = pr.readReporter(dbconn, key=args.reporter, printQuery=args.debug)

if not args.db_conf and (args.lat and args.lon):
    reporter = pr.Reporter(name='bodge', lat=args.lat, lon=args.lon, url='',
                           location="", mytype='')
#if args.datafile and not args.db_conf:
#    print("When specifying an input file, a database connection is needed")
#    exit(-1)

if not args.datafile:
    #
    # Set up the acquisition loop
    #
    samps_taken = 0
    while samps_taken < args.num_samps or args.num_samps < 0:
        t1 = time.time()
        planereps = []
        if args.vrs_fmt:
            myparams = {'fDstL': args.minDistance,  'fDstU': args.maxDistance/1000, 'lat': reporter.lat, 'lng': reporter.lon,
                        'fAltL': args.minAltitude/pr.FEET_TO_METRES, 'fAltU': args.maxAltitude/pr.FEET_TO_METRES}
            if args.debug:
                print("myparams: ", myparams)
            try:
                planereps = pr.getPlanesFromURL(args.dump1090url, myparams=myparams, mytimeout=args.mytimeout)
            except requests.exceptions.Timeout:
                if args.debug:
                    print("Timeout!")
        else:
            try:
                planereps = pr.getPlanesFromURL(args.dump1090url, mytimeout=args.mytimeout)
            except requests.exceptions.Timeout:
                if args.debug:
                    print("Timeout!")
                
        sample_timestamp = int(time.time())
        for plane in planereps:
            #
            # Do some sanity checks (valid bearing and pos, altitude, distance)
            #
            if plane.validposition and plane.validtrack and plane.seen < args.boredom_threshold and \
                    plane.altitude <= args.maxAltitude and plane.altitude >= args.minAltitude and \
                    plane.speed <= int(args.maxSpeed) and plane.speed >= int(args.minSpeed) and \
                    (not reporter or (plane.distance(reporter) >= args.minDistance and plane.distance(reporter) <= args.maxDistance)):
                if plane.time == 0:
                    plane.time = sample_timestamp - plane.seen
                plane.reporter = args.reporter
                if args.db_conf and dbconn:
                    plane.logToDB(dbconn, printQuery=args.debug)
                else:
                    print(plane.to_JSON())
            else:
                if args.debug:
                    print("Dropped report " + plane.to_JSON())
        samps_taken += 1
        if args.db_conf and dbconn:
            dbconn.commit()
        t2 = time.time()
        if samps_taken < args.num_samps or args.num_samps < 0:
            if (t2 - t1) < args.boredom_threshold:
                time.sleep(args.boredom_threshold - (t2 - t1))
else:
    inputfile = pr.openFile(args.datafile)
    data = pr.readFromFile(inputfile, numRecs=args.numrecs)
    while data:
        for plane in data:
            if not plane.reporter:
                plane.reporter = args.reporter
            if dbconn:
                plane.logToDB(dbconn, printQuery=args.debug)
            else:
                print(plane.to_JSON())
        if dbconn:
            dbconn.commit()
        data = pr.readFromFile(inputfile, numRecs=args.numrecs)
