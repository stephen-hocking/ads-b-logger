#! /usr/bin/env python3
#
# Script to pull in planes from VRS servers (inc. adsbexchange.com)
#

import argparse
import PlaneReport as pr
import datetime
from datetime import date, timedelta
import time
import json
import requests



parser = argparse.ArgumentParser(
    description="Extract previously recorded plane positions from a VRS ADS-B server")
parser.add_argument('-i', '--sample-interval', type=int, dest='boredom_threshold',
                    help="Number of seconds between each sample - default is 1", default=1)
parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-c', '--sample-count', type=int, dest='num_samps',
                    help="Number of samples to collect (-1 for infinity) - default is 1", default=1)
parser.add_argument('-t', '--start-time', dest='start_time',
                    help="The start of the time window from which records shall be retrieved, default 00:01 today")
parser.add_argument('-T', '--end-time', dest='end_time',
                    help="The end of the time window from which records shall be retrieved - default now")
parser.add_argument('-x', '--hex', dest='hexcodes',
                    help="The ICAO24 code(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-f', '--flights', dest='flights',
                    help="The flight numbers(s) of the aircraft to be singled out, separated by commas")
parser.add_argument('-d', '--min-distance', dest='minDistance', default=0,
                    help="Minimum distance that the aircraft has to be from a specified reporting point. Units are in kms")
parser.add_argument('-D', '--max-distance', dest='maxDistance', default=450.0,
                    help="Maximum distance that the aircraft has to be from a specified reporting point (expressed as lat/lon). Units are in kms")
parser.add_argument('-A', '--max-altitude', dest='maxAltitude',
                    help="The aircraft has to be at an altitude lower than this (Units are in metres)", type=float)
parser.add_argument('-a', '--min-altitude', dest='minAltitude',
                    help="The aircraft has to be at an altitude higher than this (Units are in metres)", type=float)
parser.add_argument('-n', '--num-recs', dest='numRecs',
                    help="Number of records to read at a time(defaults to 100)", default=100, type=int)
parser.add_argument('--max-speed', dest='maxSpeed',
                    help="The aircraft has to be at a speed less than or equal  than this (Units are in km/h)", type=float)
parser.add_argument('--min-speed', dest='minSpeed',
                    help="The aircraft has to be at a speed greater than or equal than this (Units are in km/h)", type=float)
parser.add_argument('--lat', dest='lat',
                    help="Latitude of the centre of the area we are interested in", type=float)
parser.add_argument('--lon', dest='lon',
                    help="Longitude of the centre of the area we are interested in", type=float)
parser.add_argument('--reporter', dest='reporter',
                    help="Name that record has as reporter (default adsbexchg)", default='adsbexchg')
parser.add_argument('-u', '--url', dest='vrs_url', default="http://public-api.adsbexchange.com/VirtualRadar/AircraftList.json",
                    help="A URL presented by a machine running VRS, e.g. http://somebox/VirtualRadar/AircraftList.json")
args = parser.parse_args()

if (args.lat and not args.lon) or (args.lon and not args.lat):
    print("Need both lon and lat arguments!")
    exit(1)
    
myparams = {'fDstL': args.minDistance,  'fDstU': args.maxDistance, 'lat': -35.343135, 'lng': 149.141059}
#urlstr = args.vrs_url + "?lat=-35.343135&trFmt=fs&trFmt=fa&lng=149.141059&fDstL=0&fDstU=100"

urlstr = args.vrs_url

response = requests.get(urlstr, params=myparams)
data = json.loads(response.text)
cur_time = time.time()
for i in data['acList']:
    try:
        mytime = i['PosTime'] / 1000
    except KeyError:
        continue
    try:
        hex = i['Icao'].lower()
    except KeyError:
        continue
    try:
        altitude = i['Alt']
    except KeyError:
        continue
    try:
        speed = i['Spd']
    except KeyError:
        continue
    try:
        squawk = i['Sqk']
    except KeyError:
        continue
    if 'Call' in i:
        flight = i['Call']
    else:
        flight = '          '
    try:
        track = i['Trak']
    except KeyError:
        continue
    try:
        lon = i['Long']
    except KeyError:
        continue
    try:
        lat = i['Lat']
    except KeyError:
        continue

    try:
        isGnd = i['Gnd']
    except KeyError:
        continue
    
    validposition = 1
    validtrack = 1
    reporter  = args.reporter
    try:
        messages = i['CMsgs']
    except KeyError:
        continue
    if 'Mlat' in i:
        mlat = i['Mlat']
    else:
        mlat = False
    if 'Vsi' in i:
        vert_rate = i['Vsi']
    else:
        vert_rate = 0.0
    isMetric = False
    seen = seen_pos = (cur_time - mytime)
    if args.debug:
        print ("cur_time:", cur_time, " mytime:", mytime, " seen:", seen)


    if seen < args.boredom_threshold:
        planerep = pr.PlaneReport(hex=hex, time=mytime, speed=speed, squawk=squawk, flight=flight, altitude=altitude,
                                  track=track, lon=lon, lat=lat, vert_rate=vert_rate, seen=seen,
                                  validposition=validposition, validtrack=validtrack, reporter=reporter,
                                  report_location=None, messages=messages, seen_pos=seen_pos, category=None)
        print(planerep.to_JSON())
        if args.debug:
            print(i)

#print(data)
