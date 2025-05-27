#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr
from shapely.geometry import Point

parser = argparse.ArgumentParser(
    description="Find airports withion a given distance from a location (either lat/lon pair or reporter)")

parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-r', '--reporter', dest='reporter',
                    help="A reporter to use as a point")
parser.add_argument('--lat', dest='latitude',
                    help="Latitude of point to calc distances from",
                    type=float)

parser.add_argument('--lon', dest='longitude',
                    help="Longitude of point to calc distances from",
                    type=float)

parser.add_argument('--sort-order', dest='sortOrder',
                    help="What to sort by (dist, name, icao)",
                    default=None)

parser.add_argument('-d', '--distance', dest='distance',
                    help="Max distance (default=300km)", default=300.0,
                    type=float)

parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")

args = parser.parse_args()

if (not args.latitude and not args.reporter) or (not args.longitude and not args.reporter):
    print("Need a location of some sort - either reporter or lat/lon pair")
    exit(1)

if not args.db_conf:
    print("Need a dbconfig file to read database!")
    exit(1)

dbconn = pr.connDB(args.db_conf)

if args.latitude and args.longitude:
    point = Point(args.longitude, args.latitude)
    reporter = pr.Reporter(name="", type="", lon=args.longitude, lat=args.latitude,
                           location=point.wkb_hex, url="", mytype="")
else:
    reporter = pr.readReporter(dbconn, key=args.reporter, printQuery=args.debug)

if args.debug:
    print(reporter.to_JSON())

postSql = None

if args.sortOrder:
    if args.sortOrder == "name":
        postSql = "order by name"
    elif args.sortOrder == "icao":
        postSql = "order by icao"
    elif args.sortOrder == "dist":
        postSql = "order by ST_Distance(location, '%s')" % reporter.location
    else:
        print("sort order requires one of dist, icao or name")
        exit(1)


airports = pr.readAirport(dbconn, key='%', maxDistance=(args.distance * 1000.0),
                          reporterLocation=reporter.location, printQuery=args.debug,
                          postSql=postSql)

print(len(airports))
for airport in airports:
    print(airport.icao, airport.lat, airport.lon, airport.altitude, reporter.distance(airport) / 1000.0, airport.name)

#airport_list = pr.readAirport(dbconn, args.airport, printQuery=args.debug, maxDistance=args.distance, reporterLocation=reporter.)


