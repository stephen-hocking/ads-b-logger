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
import psycopg2
from psycopg2.extras import RealDictCursor
#
# Build a list of stats for the day for a given reporter
#
parser = argparse.ArgumentParser(
    description="List stats for a given reporter on a given day")
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
parser.add_argument('-d', '--date', dest='date', default=False,
                    help="The date we're interested in for the flights")
parser.add_argument('-q', '--quiet', action="store_true", dest='quiet', default=False,
                    help="Keep the noise to a minimum")

args = parser.parse_args()

dbconn = pr.connDB(args.db_conf)
if not dbconn:
    print("Can't make connection to db")
    exit(1)

if not args.date:
    args.date = str(date.today())

reporter = pr.readReporter(dbconn, args.reporter)
if not reporter:
    print("Unable to read reporter from DB!")
    exit(1)
print(reporter.to_JSON())

sql = '''
 select max(ST_Distance(a.reporter_location, b.report_location)) as max_dist,max(b.altitude)
 as max_alt,max(b.speed) as max_speed,count(*) from reporter a, planereports b where a.name like '%s'
 and a.name = b.reporter and b.report_epoch >=
 date_part('epoch', timestamp with time zone '%s 00:00:00')::int 
 and b.report_epoch <= date_part('epoch', timestamp with time zone '%s 23:59:59')::int;''' % (pr.RPTR_FMT.format(args.reporter), args.date, args.date)

cur = dbconn.cursor(cursor_factory=RealDictCursor)
if args.debug:
    print(cur.mogrify(sql))
cur.execute(sql)

maxes = cur.fetchone()
cur.close()
print(maxes)

cur = pr.queryReportsDB(dbconn, myStartTime=args.date + " 00:00:00",
                        myEndTime=args.date + " 23:59:59",
                        myReporter=args.reporter, minDistance=maxes['max_dist'],
                        maxDistance=maxes['max_dist'], reporterLocation=reporter.location,
                        printQuery=args.debug)

max_dist_rec = cur.fetchone()
cur.close()
plane_dist = pr.PlaneReport(**max_dist_rec)
print(plane_dist.to_JSON())

cur = pr.queryReportsDB(dbconn, myStartTime=args.date + " 00:00:00", myEndTime=args.date + " 23:59:59",
                        myReporter=args.reporter, minAltitude=maxes['max_alt'],
                        maxAltitude=maxes['max_alt'], printQuery=args.debug)

max_alt_rec = cur.fetchone()
plane_alt = pr.PlaneReport(**max_alt_rec)
print(plane_alt.to_JSON())

cur = pr.queryReportsDB(dbconn, myStartTime=args.date + " 00:00:00", myEndTime=args.date + " 23:59:59",
                        myReporter=args.reporter, minSpeed=maxes['max_speed'],
                        maxSpeed=maxes['max_speed'], printQuery=args.debug)

max_speed_rec = cur.fetchone()
cur.close()
plane_speed = pr.PlaneReport(**max_speed_rec)
print(plane_speed.to_JSON())
