#! /usr/bin/env python3
#
# Load airports and runways from an apt.dat style file
#
"""
Attempts to locate a given airport in the apt.dat file and optionally insert it into the database.
"""
import argparse
import PlaneReport as pr
import datetime
import time
from datetime import date, timedelta
from geographiclib.geodesic import Geodesic
import math

def runwaypolygon(width, lat1, lon1, lat2, lon2):
    geod = Geodesic.WGS84
    g = geod.Inverse(lat1, lon1, lat2, lon2)
    bearing = g['azi1']
    b1 =  bearing + 90.0
    if b1 >= 360.0:
        b1 = b1 - 360.0
    b2 = bearing - 90.0
    if b2 < 0.0:
        b2 = b2 + 360.0
    d1 = geod.Direct(lat1, lon1, b1, width / 2.0)
    cnr1lat = d1['lat2']
    cnr1lon = d1['lon2']
    d2 = geod.Direct(lat1, lon1, b2, width / 2.0)
    cnr2lat = d2['lat2']
    cnr2lon = d2['lon2']
    d3 = geod.Direct(lat2, lon2, b2, width / 2.0)
    cnr3lat = d3['lat2']
    cnr3lon = d3['lon2']
    d4 = geod.Direct(lat2, lon2, b1, width / 2.0)
    cnr4lat = d4['lat2']
    cnr4lon = d4['lon2']
     
    runwaypoly = [(cnr1lat, cnr1lon), (cnr2lat, cnr2lon),
              (cnr3lat, cnr3lon), (cnr4lat, cnr4lon)]
    return runwaypoly

def helipadpolygon(lat, lon, bearing, length, width):
    geod = Geodesic.WGS84
    b1 = bearing
    b2 = bearing - 180.0
    if b2 < 0.0:
        b2 = b2 + 360.0
    d =  geod.Direct(lat, lon, b1, length / 2.0)
    ta1 = d['lat2']
    to1 = d['lon2']
    d =  geod.Direct(lat, lon, b2, length / 2.0)
    ta2 = d['lat2']
    to2 = d['lon2']
    return runwaypolygon(width, ta1, to1, ta2, to2)

def returnmidpoint(lat1, lon1, lat2, lon2):
    g = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2);
    # Compute midpoint starting at 1
    h1 = Geodesic.WGS84.Direct(lat1, lon1, g['azi1'], g['s12']/2);
    return h1['lat2'], h1['lon2']
 
#
# Build a description of an airport with a list of runways. Take the location of
# the airport as the midpoint of the 1st runway
#
def buildAirportRunways (fp, record):
    airport = {}
    airport['icao'] = str(record[4])
    airport['name'] = " ".join(map(str, record[5:]))
    airport['altitude'] = float(record[1]) * pr.FEET_TO_METRES
    airport['city'] = ""
    airport['country'] = ""
    airport['iata'] = ""
    runways = []
    geod = Geodesic.WGS84

    for line in fp:
        rec = line.split()
        if len(rec) > 0:
            #
            # Another airport, so finish up
            #
            if rec[0] == "1" or rec[0] == "16" or rec[0] == "17":
                break
            #
            # Land based runways
            #
            if rec[0] == "100" or rec[0] == "101" or rec[0] == "102":
                runway = {}
                end1 = ""
                end2 = ""
                if rec[0] == "100":
                    width = float(rec[1])
                    end1 = rec[8]
                    lat1 = float(rec[9])
                    lon1 = float(rec[10])
                    end2 = rec[17]
                    lat2 = float(rec[18])
                    lon2 = float(rec[19])
                    runway['poly'] = runwaypolygon(width, lat1, lon1, lat2, lon2)
                    runway['lat'], runway['lon'] = returnmidpoint(lat1, lon1, lat2, lon2)
                    g = geod.Inverse(lat1, lon1, lat2, lon2)
                    runway['heading'] = g['azi1']
                 #
                # Water based runways
                #
                if rec[0] == "101":
                    width = float(rec[1])
                    end1 = str(rec[3])
                    lat1 = float(rec[4])
                    lon1 = float(rec[5])
                    end2 = str(rec[6])
                    lat2 = float(rec[7])
                    lon2 = float(rec[8])
                    runway['poly'] = runwaypolygon(width, lat1, lon1, lat2, lon2)
                    runway['lat'], runway['lon'] = returnmidpoint(lat1, lon1, lat2, lon2)
                    g = geod.Inverse(lat1, lon1, lat2, lon2)
                    runway['heading'] = g['azi1']
                #
                # Helipad
                #
                if rec[0] == "102":
                    end1 = rec[1]
                    heading = float(rec[4])
                    lat = float(rec[2])
                    lon = float(rec[3])
                    width = float(rec[6])
                    length = float(rec[5])
                    runway['poly'] = helipadpolygon(lat, lon, heading, length, width)
                    runway['lat'] = lat
                    runway['lon'] = lon
                    runway['heading'] = heading

                runway['name'] = " ".join(map(str, [end1, end2])).rstrip()
                runway['airport'] = airport['icao']
                runways.append(runway)
                
        #
    airport['lat'] = runways[0]['lat']
    airport['lon'] = runways[0]['lon']
    return airport, runways, rec

parser = argparse.ArgumentParser(
    description="Read an apt.dat formatted file and load airport & runway definitions into the database.")
parser.add_argument('-y', '--db-conf-file', dest='db_conf',
                    help="A yaml file containing the DB connection parameters")
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-A', '--airport', dest='airport',
                    help="The ICAO code for the airport we are interested in")
parser.add_argument('-l', '--log-to-db', action="store_true", dest='logToDB', default=False,
                    help="Only list events, don't log them to the DBLog events to DB \
                    (default is to only print them out)")
parser.add_argument('-n', '--num-recs', dest='numRecs',
                    help="Number of records to read at a time(defaults to 100)", default=100)
parser.add_argument('-j', '--json', action="store_true", dest='printJSON', default=False,
                    help="print records in JSON format (default is to print as text)")
parser.add_argument('-q', '--quiet', action="store_true", dest='quiet', default=False,
                    help="If chosen, don't print any output (default is false)")
parser.add_argument('-u', '--update', action="store_true", dest='update',
                    default=False, help="Update the reporter data, rather than create it")

parser.add_argument('-f', '--file', dest='datafile', help='Input datafile')


args = parser.parse_args()

dbconn = None

if not args.db_conf and (args.logToDB or args.update):
    print("A valid URL db configuration file is needed!")
    exit(1)

if not args.datafile:
    print("A datafile is required!")
    exit(1)

if args.db_conf:
    dbconn = pr.connDB(args.db_conf)

#if not args.airport:
#    print("An Airport is needed!")
#    exit(1)

inputfile = pr.openFile(args.datafile)

for line in inputfile:
    record = line.split()
    if len(record) > 0:
        if record[0] == "1" or record[0] == "16" or record[0] == "17":
            while len(record) > 5:
                if record[4] == args.airport:
                    airport, runways, record = buildAirportRunways(inputfile, record)
                    airportrec = pr.Airport(icao=airport['icao'], iata=airport['iata'], name=airport['name'],
                                         city=airport['city'], country=airport['country'], altitude=airport['altitude'],
                                         lon=airport['lon'], lat=airport['lat'])
                    if dbconn:
                        airportrec.logToDB(dbconn, printQuery=args.debug, update=args.update)
                        dbconn.commit()
                        for runway in runways:
                            runwayrec = pr.Runway(airport=runway['airport'], name=runway['name'],
                                                  heading=runway['heading'], runway_points=runway['poly'],
                                                  lat=runway['lat'], lon=runway['lon'])
                            runwayrec.logToDB(dbconn, printQuery=args.debug, update=args.update)
                    if dbconn:
                        dbconn.commit()
                    exit(0)
                elif not args.airport:
                    airport, runways, record = buildAirportRunways(inputfile, record)
                    if dbconn:
                        airportrec = pr.Airport(icao=airport['icao'], iata=airport['iata'], name=airport['name'],
                                         city=airport['city'], country=airport['country'], altitude=airport['altitude'],
                                         lon=airport['lon'], lat=airport['lat'])
                        airportrec.logToDB(dbconn, printQuery=args.debug, update=args.update)
                        dbconn.commit()
                        for runway in runways:
                            runwayrec = pr.Runway(airport=runway['airport'], name=runway['name'],
                                                  heading=runway['heading'], runway_points=runway['poly'],
                                                  lat=runway['lat'], lon=runway['lon'])
                            runwayrec.logToDB(dbconn, printQuery=args.debug, update=args.update)
                    if dbconn:
                        dbconn.commit()
                    print(airport)
                    print(runways)
                else:
                    break
                    


        
