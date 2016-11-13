#! /usr/bin/env python3
#
#
import argparse
import datetime
from datetime import date, timedelta
import PlaneReport as pr

del_count = 0

def procPlaneDist(planes, debug=False):
    """
    Take a list of planereports for a particular plane, find those are an anomalous
    distance wise (i.e. too far away for the speed & time) and delete them.

    Args:
        planes: List of planereports in period for one plane
        dbconn: Connection to PostGIS DB
        debug: Controls prining of debug statements

    Returns:
        List of planes to delete

    """
    KMH_TO_MPS = 3.6     # km/h to metres per second
    
    num_elems = len(planes)
    del_count = 0
    del_list =[]
    if debug:
        print ("Checking", num_elems, "of plane", planes[0].hex)
    #
    # Usually only one postion report can get munged at a time,
    # so a sliding window of 3 should be OK.
    #
    # if dist between 1st & 2nd plane is sus, bust dist between 2nd & 3rd is OK,
    # chuck 1st plane.
    # if dist between 1st & 2nd is sus, and between 2nd & 3rd is sus, but
    # dist between 1st & 3rd is OK, chuck 2nd
    # if dist between 1st & 2nd is OK, but dist between 2nd & 3rd is sus,
    # chuck 3rd.
    #
    # When deleting elements from the list, start from the last one
    # in the window, otherwise later deletions may not delete what you
    # think you're deleting!
    #
    # Fudge factor of 50km is required as various pieces of a plane report
    # are assembled at different times
    FUDGE_FACTOR = 50000
    i = 0
    while (i + 2) < num_elems:
        dist1_2 = planes[i].distance(planes[i + 1])
        maxdist1_2 = (((planes[i + 1].time - planes[i].time) *
                      max(planes[i].speed, planes[i + 1].speed)) / KMH_TO_MPS) + FUDGE_FACTOR
        dist2_3 = planes[i + 1].distance(planes[i + 2])
        maxdist2_3 = (((planes[i + 2].time - planes[i + 1].time) *
                      max(planes[i + 1].speed, planes[i + 2].speed)) / KMH_TO_MPS) + FUDGE_FACTOR
        dist1_3 = planes[i].distance(planes[i + 2])
        maxdist1_3 = (((planes[i + 2].time - planes[i].time) *
                      max(planes[i].speed, planes[i + 2].speed)) / KMH_TO_MPS) + FUDGE_FACTOR
        if debug:
            print(dist1_2 - maxdist1_2, dist2_3 - maxdist2_3, dist1_3 - maxdist1_3)
            print("plane", i, planes[i].lat, planes[i].lon, planes[i].time, planes[i].speed)
            print("plane", i + 1, planes[i + 1].lat, planes[i + 1].lon, planes[i + 1].time, planes[i + 1].speed)
            print("plane", i + 2, planes[i + 2].lat, planes[i + 2].lon, planes[i + 2].time, planes[i + 2].speed)
        #
        # Is 3rd plane an anonomaly?
        #
        if dist2_3 > maxdist2_3 and dist1_2 <= maxdist1_2:
            if debug:
                print("Deleting plane", planes[i + 2].to_JSON())
            del_list.append(planes[i + 2])
            del planes[i + 2]
            del_count += 1
            num_elems = len(planes)
        #
        # Is 2nd plane an anonomaly?
        #
        elif (dist1_2 > maxdist1_2 and dist2_3 > maxdist2_3 and dist1_3 <= maxdist1_3) or \
                 (dist1_2 > maxdist1_2 and dist1_3 < maxdist1_3 and dist2_3 < maxdist2_3):
            if debug:
                print("Deleting plane", planes[i + 1].to_JSON())
            del_list.append(planes[i + 1])
            del planes[i + 1]
            del_count += 1
            num_elems = len(planes)
        #
        # Is 1st plane the dud?
        #
        elif dist1_2 > maxdist1_2 and dist2_3 <= maxdist2_3:
            if debug:
                print("Deleting plane", planes[i].to_JSON())
            del_list(planes[i])
            del planes[i]
            del_count += 1
            num_elems = len(planes)
        else:
            i += 1    # We can safely increment index

    return del_list

def procPlaneAlt(planes, debug=False):
    """
    Take a list of planereports for a particular plane, find those are anonamolouse
    altitude wise (sudden extreme change that only lasts for a few reports) and delete them.

    Args:
        planes: List of planereports in period for one plane
        debug: Controls printing of debug statements

    Returns:
        A list of planereports to be deleted.
    """
    # Look if the altitude changes by more than this a second.
    ALT_MARGIN = 50
    num_elems = len(planes)
    del_count = i = 0
    del_list = []
    if debug:
        print ("Checking", num_elems, "of plane", planes[0].hex)
    #
    # Look for short runs of an altitude that is weirdly different from previous
    # and subsequent ones.
    #
    # If altitude changes by more than this a second...
    ALT_MARGIN = 50
    oldAlt = 0
    cur_alt_count = 0
    i = 0

    return del_list

    
def procPlaneSpeed(planes, debug=False):
    """
    Take a list of planereports for a particular plane, find those are anonamolous
    speed wise (sudden extreme change that only lasts for a few reports) and delete them.

    Args:
        planes: List of planereports in period for one plane
        debug: Controls prining of debug statements

    Returns:
        A list of planereports to be deleted.
    """
    # Look if the speed changes by more than this a second.
    SPEED_MARGIN = 50
    num_elems = len(planes)
    del_count = i = 0
    del_list = []
    if debug:
        print ("Checking", num_elems, "of plane", planes[0].hex)
    #
    # Look for short runs of an altitude that is weirdly different from previous
    # and subsequent ones.
    oldSpeed = 0
    cur_speed_count = 0
    i = 0

    return del_list

    
    
    



parser = argparse.ArgumentParser(
    description="Clean out records which look corrupt (greater that 400kms away, less than 0 metres altitiude")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-t', '--start-time', dest='start_time',
                    help="The start of the time window from which records shall be retrieved, default 00:01 yesterday")
parser.add_argument('-T', '--end-time', dest='end_time',
                    help="The end of the time window from which records shall be retrieved - default 23:59:59 yesterday")
parser.add_argument('-x', '--hex', dest='hexcodes',
                    help="The ICAO24 code(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-f', '--flights', dest='flights',
                    help="The flight numbers(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-d', '--min-distance', dest='minDistance',
                    help="Minimum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres",
                    default=450000.0, type=float)
parser.add_argument('-D', '--max-distance', dest='maxDistance',
                    help="Maximum distance that the aircraft has to be from a specified reporting point (which defaults to Home1). Units are in metres", type=float)
parser.add_argument('-A', '--max-altitude', dest='maxAltitude',
                    help="The aircraft has to be at an altitude lower than this (Units are in metres)", type=float)
parser.add_argument('-a', '--min-altitude', dest='minAltitude',
                    help="The aircraft has to be at an altitude higher than this (Units are in metres)", type=float)
parser.add_argument('-S', '--max-speed', dest='maxSpeed',
                    help="The aircraft has to be at a speed lower than this (Units are in km/h)", default=3500.0, type=float)
parser.add_argument('-s', '--min-speed', dest='minSpeed',
                    help="The aircraft has to be at a speed greater than this (Units are in km/h)", type=float)
parser.add_argument('-l', '--list-only', action="store_true", dest='list',
                    default=False, help="Only list the records to be cleaned, do not delete")
parser.add_argument('-n', '--num-recs', dest='numRecs',
                    help="Number of records to read at a time(defaults to 100)", default=100, type=int)
parser.add_argument('-r', '--reporter', dest='reporter',
                    help="Name of the reporting data collector (defaults to Home1)", default="Home1")
parser.add_argument('--track-plane', dest='track_plane', action="store_true",
                    help="Go through each of a plane's position reports, and toss out the ones that are \
                    not at a sensible distance from the reports on either side", default=False)



args = parser.parse_args()

if not args.db_conf:
    print("A valid URL db configuration file is needed!")
    exit(-1)
else:
    yesterday = datetime.date.today() - timedelta(1)
    dbconn = pr.connDB(args.db_conf)
    reporter = pr.readReporter(dbconn, args.reporter)
    if not args.start_time:
        args.start_time = yesterday.strftime("%F") + " 00:00:00"
    if not args.end_time:
        args.end_time = yesterday.strftime("%F") + " 23:59:59"

    postSql = " or altitude < 0 or speed > %s " %  args.maxSpeed
    cur = pr.queryReportsDB(dbconn, myhex=args.hexcodes, myStartTime=args.start_time, myEndTime=args.end_time,
                            myflight=args.flights, minDistance=args.minDistance, maxDistance=args.maxDistance,
                            myReporter=args.reporter, reporterLocation=reporter.location, printQuery=args.debug, postSql=postSql)
    data = pr.readReportsDB(cur, args.numRecs)
    while data:
        for plane in data:
            if args.debug or args.list:
                print("Deleting distance problem " + plane.to_JSON())
            if not args.list:
                plane.delFromDB(dbconn, printQuery=args.debug)
            del_count += 1
        data = pr.readReportsDB(cur, args.numRecs)
    dbconn.commit()
    cur.close()


    #
    # Trying to assume position & reported speed can bear some relationship has proven to be unwise...
    #
    if args.track_plane:

        postSql = " order by hex, report_epoch"
        oldplane = None
        planelist = []
        dodgy_planes = []

        cur = pr.queryReportsDB(dbconn, myhex=args.hexcodes, myStartTime=args.start_time, myEndTime=args.end_time,
                                myflight=args.flights, printQuery=args.debug, postSql=postSql)

        data = pr.readReportsDB(cur, args.numRecs)

        while data:
            for plane in data:
                if args.debug:
                    print(plane.to_JSON())
                if not oldplane or oldplane.hex != plane.hex:
                    if oldplane:
                        dodgy_planes = procPlaneDist(planelist, debug=args.debug)
                        del_count += len(dodgy_planes)
                        planelist = []
                        planelist.append(plane)
                        oldplane = plane
                    else:
                        oldplane = plane
                else:
                    planelist.append(plane)
            
            data = pr.readReportsDB(cur, args.numRecs)

        if planelist:
            dodgy_planes = procPlaneDist(planelist, dbconn, debug=args.debug, listOnly=args.list)
            del_count += len(dodgy_planes)
    
        dbconn.commit()
        cur.close()

    print("Deleted records", del_count)
