"""
Module containing classes to do with logging position reports from aircraft,
and the various entities that they interact with.
"""
import json
import requests
# from collections import namedtuple
import psycopg2
from psycopg2.extras import RealDictCursor
import time
import yaml
import sys
import io
from math import radians, cos, sin, asin, sqrt
from geographiclib.geodesic import Geodesic


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    Returned units are in metres. Differs slightly from PostGIS geography
    distance, which uses a spheroid, rather than a sphere.
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2.0) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2.0) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in metres. Use 3956 for miles
    return c * r

#
# Use geographiclib for distance
#
def geodistance(lon1, lat1, lon2, lat2):
    geod = Geodesic.WGS84

    g = geod.Inverse(lat1, lon1, lat2, lon2)
    return g['s12']

#
# Conversion constants to get rid of archaic units
#
KNOTS_TO_KMH = 1.852
FEET_TO_METRES = 0.3048

RPTR_FMT = "{:10.10}"
FLT_FMT = "{:8.8}"
SQHEX_FMT = "{:6.6}"

#
# A number of diffent implementations of dump1090 exist,
# offering varying amounts of info from http://localhost:8080/data.json
# the dump1090mutable has a far richer json interface, where the planes are
# found via http://localhost:8080/data/aircraft.json, which is itself
# a multilevel JSON document.
#
DUMP1090_MIN = ["hex", "lat", "lon", "altitude", "track", "speed"]
DUMP1090_ANTIREZ = DUMP1090_MIN + ["flight"]
DUMP1090_MALROBB = DUMP1090_ANTIREZ + ["squawk", "validposition", "vert_rate",
                                       "validtrack", "messages", "seen"]
DUMP1090_PIAWARE = DUMP1090_MALROBB + ["mlat"]
MUTABLE_EXTRAS = ["nucp", "seen_pos", "category", "rssi"]
DUMP1090_FULLMUT = DUMP1090_MALROBB + MUTABLE_EXTRAS
DUMP1090_MINMUT = ["hex", "rssi", "seen"]
# The mutable branch has variable members in each aircraft list.
MUTABLE_TRYLIST = list(set(DUMP1090_FULLMUT) - set(DUMP1090_MINMUT))
DUMP1090_DBADD =  ["isMetric", "time", "reporter", "isGnd", "report_location"]
DUMP1090_DBLIST = list(set(DUMP1090_PIAWARE + DUMP1090_DBADD) - set(["seen"]))
DUMP1090_FULL = DUMP1090_FULLMUT + DUMP1090_DBADD
VRS_KEYWRDS = ["PosTime", "Icao", "Alt", "Spd", "Sqk", "Trak", "Long", "Lat", "Gnd",
              "CMsgs", "Mlat"]
VRSFILE_KEYWRDS = VRS_KEYWRDS + ["Cos", "TT"]
              


class PlaneReport(object):
    """
    Class that deals with plane position reports, origination from the data.json interface
    of dump1090

    Creates objects from JSON structures either from dump1090, a file or a DB
    """

    hex = None
    altitude = 0.0
    speed = 0.0
    squawk = None
    flight = None
    track = 0
    lon = 0.0
    lat = 0.0
    vert_rate = 0.0
    seen = 9999999
    validposition = 1
    validtrack = 1
    time = 0
    reporter = None
    report_location = None
    isMetric = False
    messages = 0
    seen_pos = -1
    category = None
 
    def __init__(self, **kwargs):
        for keyword in DUMP1090_FULL:
            try:
                setattr(self, keyword, kwargs[keyword])
            except KeyError:
                pass
        if not self.isMetric:
            self.convertToMetric()
        zz = getattr(self, 'isGnd', None)
        if zz is None:
            if self.altitude == 0:
                setattr(self, 'isGnd', True)
            else:
                setattr(self, 'isGnd', False)
        zz = getattr(self, 'mlat', None)
        if zz is None:
            setattr(self, 'mlat', False)
        zz = getattr(self, 'rssi', None)
        if zz is None:
            setattr(self, 'rssi', -49.5)
        zz = getattr(self, 'nucp', None)
        if zz is None:
            setattr(self, 'nucp', -1)
        

    def convertToMetric(self):
        """Converts plane report to use metric units"""
        self.vert_rate = self.vert_rate * FEET_TO_METRES
        self.altitude = int(self.altitude * FEET_TO_METRES)
        self.speed = int(self.speed * KNOTS_TO_KMH)
        self.isMetric = True

    def convertFromMetric(self):
        """Converts planereport to knots/feet"""
        self.vert_rate = self.vert_rate / FEET_TO_METRES
        self.altitude = int(self.altitude / FEET_TO_METRES)
        self.speed = int(self.speed / KNOTS_TO_KMH)
        self.isMetric = False

    def __str__(self):
        fields = ['  {}: {}'.format(k, v) for k, v in self.__dict__.iteritems()
                  if not k.startswith("_")]
        return "{}(\n{})".format(self.__class__.__name__, '\n'.join(fields))

    #
    # Creates a representation that can be loaded from a single text line
    #
    def to_JSON(self):
        """Returns a JSON representation of a planereport on one line"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, separators=(',', ':'))
#		return json.dumps(self, default=lambda o: o.__dict__,
#			sort_keys=True, indent=4)

    #
    # Log planereport to already connected DB
    #
    def logToDB(self, dbconn, printQuery=False, update=False):
        """
        Logs a plane report to a database, encoding lat/lon as a PostGIS location,

        Args:
            dbconn: An existing connection to the PostGIS DB
            printQuery: A boolean which controls the printing of the query

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        #
        # Need to extract datetime fields from time
        # Need to encode lat/lon appropriately
        #
        cur = dbconn.cursor()
        coordinates = "POINT(%s %s)" % (self.lon, self.lat)
        if update:
            params = [self.hex, self.squawk, self.flight, self.isMetric,
                      self.mlat, self.altitude, self.speed, self.vert_rate,
                      self.track, coordinates, self.messages, self.time, self.reporter,
                      self.rssi, self.nucp, self.isGnd,
                      self.hex, self.squawk, FLT_FMT.format(self.flight),
                      self.reporter, self.time, self.messages]
            sql = '''
	    UPDATE planereports SET (hex, squawk, flight, "isMetric", "isMLAT", altitude, speed, vert_rate, bearing, report_location, messages_sent, report_epoch, reporter, rssi, nucp, isgnd)
	    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_PointFromText(%s, 4326),
            %s, %s, %s, %s, %s, %s)
            WHERE hex like %s and squawk like %s and flight like %s and reporter like %s
            and report_epoch = %s and messages_sent = %s'''

        else:
            params = [self.hex, self.squawk, self.flight, self.isMetric,
                      self.mlat, self.altitude, self.speed, self.vert_rate,
                      self.track, coordinates, self.messages, self.time, self.reporter,
                      self.rssi, self.nucp, self.isGnd]
            sql = '''
	    INSERT into planereports (hex, squawk, flight, "isMetric", "isMLAT", altitude, speed, vert_rate, bearing, report_location, messages_sent, report_epoch, reporter, rssi, nucp, isgnd)
	    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_PointFromText(%s, 4326), %s, %s, %s, %s, %s, %s);'''
            
        if printQuery:
            print(cur.mogrify(sql, params))
        try:
            cur.execute(sql, params)
        except Exception as err:
            print("Error inserting ", err)

        cur.close()

    #
    # Delete record - assuming sampling once a second, the combination of
    # hex, report_epoch and reporter should be unique
    #
    def delFromDB(self, dbconn, printQuery=None):
        """
        Deletes the record that matches the plane report from the DB

        Args:
            dbconn: An existing DB connection
            printQuery:  A boolean which controls the printing of the query

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        sql = '''DELETE from planereports WHERE '''
        sql = sql + (" hex like '%s' " % self.hex)
        sql = sql + (" and flight like '%s' " % FLT_FMT.format(self.flight))
        sql = sql + (" and reporter like '%s'" %
                     RPTR_FMT.format(self.reporter))
        sql = sql + (" and report_epoch=%s " % self.time)
        sql = sql + (" and altitude=%s " % self.altitude)
        sql = sql + (" and speed=%s " % self.speed)
        sql = sql + (" and messages_sent=%s" % self.messages)
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

    #
    # Distance from another object with lat/lon
    #
    def distance(self, reporter):
        """Returns distance in metres from another object with lat/lon"""
        return geodistance(self.lon, self.lat, reporter.lon, reporter.lat)


#
# Connect to the Database
#
def connDB(yamlfile, dbuser=None, dbhost=None, dbpasswd=None, dbport=5432):
    """
    Makes a connection to a Postgres DB, dictated by a yaml file, with optional
    overides.

    Args:
        yamlfile: Filename of the yaml file (compulsory)
        dbuser: Contains name of database user to login (optional)
        dbhost: Name of host that DB is running on (optional)
        dbpasswd: Password for the DB account (optional)
        dbport: Portnumber to connect to on DB host (optional)

    Returns:
        psycopg2 DB connection

    Could do with some sprucing up. Format of yamlfile looks like:
        adsb_logger:
            dbhost: somehost.somewhere.com
            dbuser: some_username
            dbpassword: S3kr1t_P4ssw0rd
    """
    dbconn = None
    #
    # Also allow yaml file to be completely or partially overridden
    #
    if not (dbuser and dbhost and dbpasswd):
        with open(yamlfile, 'r') as db_cfg_file:
            db_conf = yaml.load(db_cfg_file)
        if not dbhost:
            dbhost = db_conf["adsb_logger"]["dbhost"]
        if not dbuser:
            dbuser = db_conf["adsb_logger"]["dbuser"]
        if not dbpasswd:
            dbpasswd = db_conf["adsb_logger"]["dbpassword"]
    connect_str = "dbname=PlaneReports user=" + dbuser + " host=" + \
        dbhost + " password=" + dbpasswd + " port=" + str(dbport)
    try:
        dbconn = psycopg2.connect(connect_str)
    except:
        print("Can't connect to plane report database with " + connect_str)
        exit(-1)
    return dbconn


def queryReportsDB(dbconn, myhex=None, myStartTime=None, myEndTime=None, myflight=None,
                   preSql=None, postSql=None, maxAltitude=None, minAltitude=None,
                   reporterLocation=None, minDistance=None, maxDistance=None,
                   myReporter=None, maxSpeed=None, minSpeed=None, minVert_rate=None,
                   maxVert_rate=None, minRssi=None, maxRssi=None, minNucp=None, maxNucp=None,
                   runways=None, printQuery=None):
    """
    Function to set up and execute a query on the DB.

    Rather long and complex, but is kinda needed in order to be able to set various
    conditions for the query that we are constructing

    Args:
        dbconn: A psycopg2 DB connection (compulsory)
        myhex: A comma separated (if multiple) list of the ICAO24 codes of the planes (optional)
        myStarTime: Look for reports after this time YYYY-MM-DD hh:mm:ss (optional)
        myEndTime: Look for reports before this time YYYY-MM-DD hh:mm:ss (optional)
        myFlight:  A comma separated (if multiple) list of the flights (optional)
        preSql: SQL code to place before the main query (optional)
        PostSql: SQL Code to place after the main query (optional)
        maxAltitude: Look for report at or below this altitude in metres (optional)
        minAltitude: Look for report at or above this altitude in metres (optional)
        reporterLocation: Location of reporter as a WKB format position.
            Required for distance queries (optional)
        minDistance: Reports at or above this distance (metres) reporterLocation
            is required (optional)
        maxDistance: Reports at or below this distance (metres) reporterLocation
            is required (optional)
        myReporter: Look for reports that were reported by this station (optional)
        maxSpeed: Look for reports of a speed at or below this in kms/h (optional)
        minSpeed: Look for reports of a speed at or above this in kms/h (optional)
        minVert_rate: Look for climb rate at or above this metres/min (optional)
        maxVert_rate: Look for climb rate at or below this metres/min (optional)
        minRssi: Look for Minimum Received Signal Strength Indicator >= this
        maxRssi: Look for Minimum Received Signal Strength Indicator <= this
        minNucp: Look for Navigation Uncertainty Category - Position >= this
        maxNucp: Look for Navigation Uncertainty Category - Position >= this
        runways: Look for reports located within this polygon WKB format (optional)
        printQuery: Display the constructed query to stdout for debugging (optional)

    Returns:
        A psycopg2 cursor pointing to the results of the query
    """
    #
    # Basic SQL query
    #
    sql = '''
		SELECT hex, squawk, flight, "isMetric", "isMLAT" as mlat, altitude, speed,
		vert_rate, bearing as track, ST_X(report_location::geometry) as lon, ST_Y(report_location::geometry)as lat,
		messages_sent as messages, report_epoch as time, reporter, report_location::geography,
                rssi, nucp, isgnd as isGnd
			FROM planereports'''

    #
    # Start adding conditionals
    #
    conditions = 0
    if myStartTime or myEndTime or myflight or myhex or (maxDistance and reporterLocation) \
           or (minDistance and reporterLocation) or maxAltitude or minAltitude or myReporter \
           or minSpeed or maxSpeed or minVert_rate or maxVert_rate or runways:
        sql = sql + " where "

    #
    # Convert time strings to UTC from local
    #
    if myStartTime:
        if conditions:
            sql = sql + " and "
        starttime = time.mktime(time.strptime(myStartTime, "%Y-%m-%d %H:%M:%S"))
        sql = sql + (" report_epoch >= %s " % int(starttime))
        conditions += 1
    if myEndTime:
        if conditions:
            sql = sql + " and "
        endtime = time.mktime(time.strptime(myEndTime, "%Y-%m-%d %H:%M:%S"))
        sql = sql + (" report_epoch <= %s " % int(endtime))
        conditions += 1

    if myhex:
        if conditions:
            sql = sql + " and "
        #
        # One or more hex codes
        #
        if myhex.find(',') != -1:
            numcommas = myhex.count(',')
            myhexs = myhex.split(',')
            sql = sql + " ("
            for i, xx in enumerate(myhexs):
                sql = sql + ("hex like '%s' " % xx)
                if i < numcommas:
                    sql = sql + " or "
            sql = sql + ")"
        else:
            sql = sql + (" hex like '%s'" % myhex)
        conditions += 1

    if myflight:
        if conditions:
            sql = sql + " and "
        #
        # we have to pad these with spaces out to 8 chars
        #
        if myflight.find(',') != -1:
            numcommas = myflight.count(',')
            myflights = myflight.split(',')
            sql = sql + " ("
            for i, ff in enumerate(myflights):
                sql = sql + ("flight like '%s' " % FLT_FMT.format(ff))
                if i < numcommas:
                    sql = sql + " or "
            sql = sql + ")"
        else:
            sql = sql + (" flight like '%s'" % FLT_FMT.format(myflight))
        conditions += 1

    if maxAltitude:
        if conditions:
            sql = sql + " and "
        sql = sql + (" altitude <= %s " % maxAltitude)
        conditions += 1
    if minAltitude:
        if conditions:
            sql = sql + " and "
        sql = sql + (" altitude >= %s " % minAltitude)
        conditions += 1

    if maxSpeed:
        if conditions:
            sql = sql + " and "
        sql = sql + (" speed <= %s " % maxSpeed)
        conditions += 1
    if minSpeed:
        if conditions:
            sql = sql + " and "
        sql = sql + (" speed >= %s " % minSpeed)
        conditions += 1

    if maxVert_rate:
        if conditions:
            sql = sql + " and "
        sql = sql + (" vert_rate <= %s " % maxVert_rate)
        conditions += 1
    if minVert_rate:
        if conditions:
            sql = sql + " and "
        sql = sql + (" vert_rate >= %s " % minVert_rate)
        conditions += 1

    if maxRssi:
        if conditions:
            sql = sql + " and "
        sql = sql + (" rssi <= %s " % maxRssi)
        conditions += 1
    if minRssi:
        if conditions:
            sql = sql + " and "
        sql = sql + (" rssi >= %s " % minRssi)
        conditions += 1

    if maxNucp:
        if conditions:
            sql = sql + " and "
        sql = sql + (" nucp <= %s " % maxNucp)
        conditions += 1
    if minNucp:
        if conditions:
            sql = sql + " and "
        sql = sql + (" nucp >= %s " % minNucp)
        conditions += 1

    if reporterLocation and minDistance and myReporter:
        if conditions:
            sql = sql + " and "
        sql = sql + (" (ST_Distance(report_location, '%s') >= %s and reporter like '%s') " %
                     (reporterLocation, minDistance, RPTR_FMT.format(myReporter)))
        conditions += 1
    if reporterLocation and maxDistance and myReporter:
        if conditions:
            sql = sql + " and "
        sql = sql + (" (ST_Distance(report_location, '%s') <= %s and reporter like '%s') " %
                     (reporterLocation, maxDistance, RPTR_FMT.format(myReporter)))
        conditions += 1

    if myReporter:
        if conditions:
            sql = sql + " and "
        sql = sql + "reporter like '%s' " % RPTR_FMT.format(myReporter)
        conditions += 1
        
    if runways:
        if conditions:
            sql = sql + " and "
        sql = sql + \
            (" ST_Contains('%s', report_location::geometry) " % runways)
        conditions += 1

    #
    # preSql and postSql are for wrapping this query inside another query
    #
    if preSql:
        sql = preSql + sql
    if postSql:
        sql = sql + postSql

    #
    # Now execute the query
    #
    # Gets us a list of JSON objects
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    return cur

def readReportsDB(cur, numRecs=100):
    """
    Read the postion reports that were returned by the query that was set up
    and executed by queryReportsDB.

    Args:
        cur: psycopg2 cursor returned by queryReportsDB.
        numRecs: Return up to this number of postion reports each call (optional)

    Returns:
        A list of PlaneReports
    """
    retlist = []
    data = cur.fetchmany(numRecs)
    planereps = [PlaneReport(**pl) for pl in data]
    for plane in planereps:
        retlist.append(plane)
    return retlist


def openFile(filename, encoding='latin-1'):
    """
    Opens a plane ordinary file, usually containing the textual representations
    of PlaneReports produced by the to_JSON method.

    Args:
        filename: Pathname of file

    Returns:
        A valid file handle
    """
    if filename == "-":
        return io.TextIOWrapper(sys.stdin.buffer, encoding=encoding)
    else:
        return open(filename, 'r', encoding=encoding)


def readFromFile(inputfile, numRecs=100):
    """
    Reads a file of PlaneReport records

    Args:
        inputfile: A filehandle returned by openFile
        numRecs: Return up to this number of records per call (optional)

    Returns:
        A list of PlaneReports
    """
    retlist = []


    for i, line_terminated in enumerate(inputfile):
        try:
            data = json.loads(line_terminated.rstrip('\n'))
        except:
            print("Faulty line ", line_terminated.rstrip('\n'))
        plane = PlaneReport(**data)
        retlist.append(plane)
        if i > numRecs:
            break
    return retlist

def readVRSFromFile(inputfile):
    """
    Reads a file of VRS records (from the daily archive)

    Args:
        inputfile: A filehandle returned by openFile

    Returns:
        A list of PlaneReports
    """
    retlist = []
    try:
        data = json.load(inputfile)
    except:
        return []
    for pl in data['acList']:
            valid = True
            for keywrd in VRSFILE_KEYWRDS:
                if keywrd not in pl:
                    valid = False
                    break
            if valid:
                mytime = pl['PosTime'] / 1000
                hex = pl['Icao'].lower()
                altitude = pl['Alt']
                speed = pl['Spd']
                squawk = pl['Sqk']
                if 'Call' in pl:
                    flight = FLT_FMT.format(pl['Call'])
                else:
                    flight = ' '
                track = pl['Trak']
                lon = pl['Long']
                lat = pl['Lat']
                isGnd = pl['Gnd']
                messages = pl['CMsgs']
                mlat = pl['Mlat']
                TT = pl['TT']

                if 'Vsi' in pl:
                    vert_rate = pl['Vsi']
                else:
                    vert_rate = 0.0
                isMetric = False
                Cos = pl['Cos']
                if TT == 'a' or TT == 's':
                    numpos = len(Cos) / 4
                    for i in range(int(numpos)):
                        if Cos[(i * 4) + 3]:
                            if TT == 'a':
                                altitude = Cos[(i * 4) + 3]
                            elif TT == 's':
                                speed = Cos[(i * 4) + 3]
                            lat = Cos[(i * 4) + 0]
                            lon = Cos[(i * 4) + 1]
                            if lat < -90.0 or lat > 90.0 or lon < -180.0 or lon > 180.0:
                                continue
                            mytime = Cos[(i * 4) + 2] / 1000
                            seen = seen_pos = 0
                            plane = PlaneReport(hex=hex, time=mytime, speed=speed, squawk=squawk, flight=flight,
                                                altitude=altitude, isMetric=False,
                                                track=track, lon=lon, lat=lat, vert_rate=vert_rate, seen=seen,
                                                validposition=1, validtrack=1, reporter="", mlat=mlat, isGnd=isGnd,
                                                report_location=None, messages=messages, seen_pos=seen_pos, category=None)
                            retlist.append(plane)
    return retlist            

def getPlanesFromURL(urlstr, myparams=None, mytimeout=0.9):
    """
    Reads JSON objects from a server at a URL (usually a dump1090 instance)

    Args:
        urlstr: A string containing a URL (e.g. http://mydump1090:8080/data.json)
        myparams: parameters used for filtering requests to adsbexchange.com

    Returns:
        A list of PlaneReports
    """
    cur_time = time.time()
    if myparams:
        response = requests.get(urlstr, params=myparams, timeout=mytimeout)
    else:
        response = requests.get(urlstr, timeout=mytimeout)
    data = json.loads(response.text)
    # Check for dump1090_mutability style of interface
    if 'aircraft' in data: 
        planereps = []
        for pl in data['aircraft']:
            #
            # See if we're dealing with 3.6.2 of piaware's version
            #
            if 'nav_altitude' in pl:
                pl['altitude'] = pl['nav_altitude']
            if 'gs' in pl: 
                pl['speed'] = pl['gs']
            if 'baro_rate' in pl:
                pl['vert_rate'] = pl['baro_rate']


            #
            # Now should have relevant attrs, so loop through and make sure
            #
            valid = True
            for keywrd in DUMP1090_MIN:
                if keywrd not in pl:
                    valid = False
                    break
            if valid:
                if pl['altitude'] == 'ground':
                    pl['altitude'] = 0
                    plane = PlaneReport(**pl)
                    setattr(plane, 'isGnd', True)
                else:
                    plane = PlaneReport(**pl)
                    setattr(plane, 'isGnd', False)
                setattr(plane, 'validposition', 1)
                setattr(plane, 'validtrack', 1)

                # mutability has mlat set to list of attrs mlat'ed - we want bool
                if 'mlat' not in pl:
                    setattr(plane, 'mlat', False)
                else:
                    setattr(plane, 'mlat', True)

                planereps.append(plane)
    # VRS style - adsbexchange.com        
    elif 'acList' in data:
        planereps = []
        for pl in data['acList']:
            valid = True
            for keywrd in VRS_KEYWRDS:
                if keywrd not in pl:
                    valid = False
                    break
            if valid:
                mytime = pl['PosTime'] / 1000
                hex = pl['Icao'].lower()
                altitude = pl['Alt']
                speed = pl['Spd']
                squawk = pl['Sqk']
                if 'Call' in pl:
                    flight = FLT_FMT.format(pl['Call'])
                else:
                    flight = ' '
                track = pl['Trak']
                lon = pl['Long']
                lat = pl['Lat']
                isGnd = pl['Gnd'] 
                messages = pl['CMsgs']
                mlat = pl['Mlat']

                if 'Vsi' in pl:
                    vert_rate = pl['Vsi']
                else:
                    vert_rate = 0.0
                isMetric = False
                seen = seen_pos = (cur_time - mytime)
                plane = PlaneReport(hex=hex, time=mytime, speed=speed, squawk=squawk, flight=flight,
                                    altitude=altitude, isMetric=False,
                                    track=track, lon=lon, lat=lat, vert_rate=vert_rate, seen=seen,
                                    validposition=1, validtrack=1, reporter="", mlat=mlat, isGnd=isGnd,
                                    report_location=None, messages=messages, seen_pos=seen_pos, category=None)
                planereps.append(plane)
                    
    else:
        planereps = [PlaneReport(**pl) for pl in data]
    return planereps



class Reporter(object):
    """
    Code for manipulating information about Reporters (the original source
    of PlaneReports)
    """

    name = "ChangeME"
    mytype = "invalid"
    lon = 0.0
    lat = 0.0
    url = ""
    location = ""

    def __init__(self, **kwargs):
        for keyword in ["name", "mytype", "lon", "lat", "url", "location"]:
            setattr(self, keyword, kwargs[keyword])

#	def __str__(self):
#	fields = ['  {}: {}'.format(k,v) for k,v in self.__dict__.iteritems()
#			if not k.startswith("_")]
#		return "{}(\n{})".format(self.__class__.__name__, '\n'.join(fields))

    def to_JSON(self):
        """Return a string containing a JSON representation of a Reporter"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, \
                          separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None, update=False):
        """
        Place an instance of a Reporter into the DB - contains name,
        type, location and URL for access

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        coordinates = "POINT(%s %s)" % (self.lon, self.lat)
        if update:
            sql = '''
            UPDATE reporter SET (name, type, reporter_location, url) =
            (%s, %s, ST_PointFromText(%s, 4326), %s) where name like %s
            '''
            params = [RPTR_FMT.format(self.name), self.mytype, coordinates, self.url,
                      RPTR_FMT.format(self.name)]
        else:
            sql = '''
            INSERT into reporter (name, type, reporter_location, url)
            VALUES (%s, %s, ST_PointFromText(%s, 4326), %s);'''
            params = [RPTR_FMT.format(self.name), self.mytype, coordinates, self.url]
        
        if printQuery:
            print(cur.mogrify(sql, params))
        try:
            cur.execute(sql, params)
        except Exception as err:
            print("Error inserting ", err)

        cur.close()

    def delFromDB(self, dbconn, printQuery=None):
        """
        Remove an instance of a Reporter from the DB.

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        sql = "DELETE from reporter WHERE name like '%s'" % self.name
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

    def distance(self, plane):
        """Returns distance in metres from another object with lat/lon"""
        return geodistance(self.lon, self.lat, plane.lon, plane.lat)


def readReporter(dbconn, key="Home1", printQuery=None):
    """
    Read an instance of a Reporter record from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        key: The name of the Reporter record (optional, defaults to Home1)
        printQuery: Triggers printing the SQL query to stdout

    Returns:
        A Reporter object with a location field in WKB format
    """
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT name, type as mytype, ST_X(reporter_location::geometry) as lon, ST_Y(reporter_location::geometry) as lat, url, reporter_location as location
			FROM reporter WHERE name like \'%s\' ''' % RPTR_FMT.format(key)

    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    data = cur.fetchone()
    if data:
        return Reporter(**data)
    else:
        return None


class Airport(object):
    """
    A Class for manipulation of Airport objects.
    """

    icao = ""
    iata = ""
    name = ""
    city = ""
    country = ""
    altitude = 0
    lon = 0.0
    lat = 0.0

    def __init__(self, **kwargs):
        for keyword in ["icao", "iata", "name", "city", "country", "altitude", "lon", "lat"]:
            setattr(self, keyword, kwargs[keyword])

    def to_JSON(self):
        """Creates a JSON representation string of the airport"""
        return json.dumps(self, default=lambda o: o.__dict__, \
                          sort_keys=True, separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None, update=None):
        """
        Inserts or updates an Airport into the DB, creating a POLYGON WKB representation
        from the list of co-ordinates supplied.

        Args:
            dbconn: psycopg2 DB connectiomn
            printQuery: Boolean to trigger printing of constructed SQL
            update: Boolean to trigger update rather than insertion of a record.

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions on error
        """
        cur = dbconn.cursor()
        coordinates = "POINT(%s %s)" % (self.lon, self.lat)
        polygon = "POLYGON (("
        num_points = 0
        # Build WKT representation from lat/lon (y/x) pairs,
        # which have to be swapped to lon/lat (x/y)
#        for i in self.runway_points:
#            if num_points > 0:
#                polygon = polygon + ", "
#            polygon = polygon + ("%s %s" % (i[1], i[0]))
#            num_points += 1
#        polygon = polygon + (", %s %s))" %
#                             (self.runway_points[0][1], self.runway_points[0][0]))
#
#        if update:
#            sql = '''
#			UPDATE airport SET (iata, name, city, country, altitude, location) =
#			(%s, %s, %s, %s, %s, ST_PointFromText(%s, 4326), ST_GeographyFromText(%s)) WHERE icao like %s'''
#            params = [self.iata, self.name, self.city, self.country, self.altitude, coordinates,
#                      polygon, self.icao]
#        else:
#            sql = '''
#			INSERT into airport (icao, iata, name, city, country, altitude, location, runways)
#			VALUES (%s, %s, %s, %s, %s, %s, ST_PointFromText(%s, 4326), ST_GeographyFromText(%s))'''
#            params = [self.icao, self.iata, self.name, self.city, self.country, self.altitude,
#                      coordinates, polygon]

        if update:
            sql = '''
			UPDATE airport SET (iata, name, city, country, altitude, location) =
			(%s, %s, %s, %s, %s, ST_PointFromText(%s, 4326)) WHERE icao like %s'''
            params = [self.iata, self.name, self.city, self.country, self.altitude, coordinates,
                      self.icao]
        else:
            sql = '''
			INSERT into airport (icao, iata, name, city, country, altitude, location)
			VALUES (%s, %s, %s, %s, %s, %s, ST_PointFromText(%s, 4326))'''
            params = [self.icao, self.iata, self.name, self.city, self.country, self.altitude,
                      coordinates]

        if printQuery:
            print(cur.mogrify(sql, params))

        try:
            cur.execute(sql, params)
        except Exception as err:
            print("Error inserting ", err)

        cur.close()

    #
    # Delete from DB
    #
    def delFromDB(self, dbconn, printQuery=None):
        """
        Deletes an Airport from the DB.

        Args:
            dbconn: psycopg2 DB connectiomn
            printQuery: Boolean to trigger printing of constructed SQL

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions on error
        """
        cur = dbconn.cursor()
        sql = "DELETE from airport WHERE icao like '%s'" % self.icao
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

    #
    # Distance from another object with lat/lon
    #
    def distance(self, plane):
        """Returns distance in metres from another object with lat/lon"""
        return geodistance(self.lon, self.lat, plane.lon, plane.lat)


def readAirport(dbconn, key, printQuery=None, preSql=None, postSql=None,
                maxAltitude=None, minAltitude=None, numRecs=40000,
                reporterLocation=None, minDistance=None, maxDistance=None):
    """
    Reads an Airport from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        key: The ICAO 4 character name for the airport
        printQuery: Boolean that triggers printing of the SQL (optional)
        preSql: SQL code to place before the main query (optional)
        PostSql: SQL Code to place after the main query (optional)
        maxAltitude: Look for report at or below this altitude in metres (optional)
        minAltitude: Look for report at or above this altitude in metres (optional)
        reporterLocation: Location of reporter as a WKB format position.
            Required for distance queries (optional)
        minDistance: Reports at or above this distance (metres) reporterLocation
            is required (optional)
        maxDistance: Reports at or below this distance (metres) reporterLocation
            is required (optional)

    Returns:
        An Airport object

    Raises:
        psycopg2 exceptions
    """
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT icao, iata, name, city, country, altitude, ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat, location
			FROM airport WHERE icao like \'%s\' ''' % key

    conditions = 1

    if maxAltitude:
        if conditions:
            sql = sql + " and "
        sql = sql + (" altitude <= %s " % maxAltitude)
        conditions += 1

    if minAltitude:
        if conditions:
            sql = sql + " and "
        sql = sql + (" altitude >= %s " % minAltitude)
        conditions += 1

    if reporterLocation and minDistance:
        if conditions:
            sql = sql + " and "
        sql = sql + (" (ST_Distance(location, '%s') >= %s ) " %
                     (reporterLocation, minDistance))
        conditions += 1

    if reporterLocation and maxDistance:
        if conditions:
            sql = sql + " and "
        sql = sql + (" (ST_Distance(location, '%s') <= %s ) " %
                     (reporterLocation, maxDistance))
        conditions += 1

    #
    # preSql and postSql are for wrapping this query inside another query
    #
    if preSql:
        sql = preSql + sql
    if postSql:
        sql = sql + postSql


    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    airport_list = []
    airports = cur.fetchmany(numRecs)
    if airports:
        for data in airports:
            airport_list.append(Airport(icao=data['icao'], iata=data['iata'], name=data['name'], city=data['city'],
                                        country=data['country'], altitude=int(data['altitude']), lat=data['lat'],
                                        lon=data['lon'], location=data[
                                            'location']))
        return airport_list
    else:
        return None


#def readAirportFromFile(inputfile):
#    """
#    Read Airport with simple polygon from a handbuilt text file
#
#    Args:
#        inputfile: Pathname of file
#
#    Returns:
#        An Airport object
#
#        Very basic - no error checking whatsoever! File format is:
#            Line 1: 4 char ICAO code for airport
#            Line 2: 3 char IATA code for airport
#            Line 3: Airport name
#            Line 4: Airport City
#            Line 5: Airport Country
#            Line 6: Airport Altitude (in metres)
#            Line 7: cordinates (lat/lon)
#            Lines 8-n: Polygon vertices enclosing runways only, not taxiways and parking

#        Should eventually write one to
#        pull it out from X-Plane apt.dat file
#    """
#    airport = {}
#    icao = inputfile.readline().strip('\n')
#    iata = inputfile.readline().strip('\n')
#    name = inputfile.readline().strip('\n')
#    city = inputfile.readline().strip('\n')
#    country = inputfile.readline().strip('\n')
#    altitude = int(inputfile.readline())
#    coords = inputfile.readline().split(",")
#    lat = float(coords[0].strip())
#    lon = float(coords[1].strip())
#    runway_points = []
#    for lines in inputfile:
#        tmp = []
#        coords = lines.rstrip('\n').split(",")
#        tmp.append(float(coords[0].strip()))
#        tmp.append(float(coords[1].strip()))
#        runway_points.append(tmp)
#
#    airport = Airport(icao=icao, iata=iata, name=name, city=city, country=country,
#                      altitude=altitude, lat=lat, lon=lon, runway_points=runway_points)
#
#    return airport

class Runway(object):
    """
    A Class for manipulation of Runway objects.
    """

    airport = ""
    name = ""
    lon = 0.0
    lat = 0.0
    heading = 0.0
    runway_area = ""
    runway_points = []

    def __init__(self, **kwargs):
        try:
            for keyword in ["airport", "name", "lon", "lat", "heading", "runway_area", "runway_area_poly",
                            "runway_points"]:
                setattr(self, keyword, kwargs[keyword])
        except:
             for keyword in ["airport", "name", "lon", "lat", "heading", "runway_points"]:
                setattr(self, keyword, kwargs[keyword])
           

    def to_JSON(self):
        """Creates a JSON representation string of the airport"""
        return json.dumps(self, default=lambda o: o.__dict__, \
                          sort_keys=True, separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None, update=None):
        """
        Inserts or updates an Airport into the DB, creating a POLYGON WKB representation
        from the list of co-ordinates supplied.

        Args:
            dbconn: psycopg2 DB connectiomn
            printQuery: Boolean to trigger printing of constructed SQL
            update: Boolean to trigger update rather than insertion of a record.

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions on error
        """
        cur = dbconn.cursor()
        coordinates = "POINT(%s %s)" % (self.lon, self.lat)
        polygon = "POLYGON (("
        num_points = 0
        # Build WKT representation from lat/lon (y/x) pairs,
        # which have to be swapped to lon/lat (x/y)
        for i in self.runway_points:
            if num_points > 0:
                polygon = polygon + ", "
            polygon = polygon + ("%s %s" % (i[1], i[0]))
            num_points += 1
        polygon = polygon + (", %s %s))" %
                             (self.runway_points[0][1], self.runway_points[0][0]))

        if update:
            sql = '''
			UPDATE runways SET (heading, location, runway_area) =
			(%s, ST_PointFromText(%s, 4326), ST_GeographyFromText(%s)) WHERE icao like '%s' and name like '%s' '''
            params = [self.heading, coordinates, polygon, self.airport, self.name]
        else:
            sql = '''
			INSERT into runways (airport, name, heading, location, runway_area)
			VALUES (%s, %s, %s, ST_PointFromText(%s, 4326), ST_GeographyFromText(%s))'''
            params = [self.airport, self.name, self.heading, coordinates, polygon]


        if printQuery:
            print(cur.mogrify(sql, params))

        try:
            cur.execute(sql, params)
        except Exception as foo:
            print("Some error", foo)


        cur.close()

    #
    # Delete from DB
    #
    def delFromDB(self, dbconn, printQuery=None):
        """
        Deletes a runway from the DB.

        Args:
            dbconn: psycopg2 DB connectiomn
            printQuery: Boolean to trigger printing of constructed SQL

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions on error
        """
        cur = dbconn.cursor()
        sql = "DELETE from runways WHERE airport like '%s' and name like '%s'" % (self.airport, self.name)
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

    #
    # Distance from another object with lat/lon
    #
    def distance(self, plane):
        """Returns distance in metres from another object with lat/lon"""
        return geodistance(self.lon, self.lat, plane.lon, plane.lat)


def readRunways(dbconn, airport, printQuery=None, numRecs=100):
    """
    Reads an airport's runways from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        airport: The conICAO 4 character name for the airport
        printQuery: Boolean that triggers printing of the SQL (optional)

    Returns:
        An list of Runway objects

    Raises:
        psycopg2 exceptions
    """
    runways = []
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT airport, name, heading, ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat, location, runway_area, ST_AsText(runway_area::geometry) as runway_area_poly
			FROM runways WHERE airport like \'%s\' ''' % airport

    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    data = cur.fetchmany(numRecs)
    if data:
        for rec in data:
            pointstr = rec['runway_area_poly'].strip("POLYGON()")
            pointlist = pointstr.split(',')
            runway_points = []
            for i in pointlist:
                j = i.split(' ')
                tmp = [float(j[1]), float(j[0])]
                runway_points.append(tmp)

                runway = Runway(airport=rec['airport'], name=rec['name'], heading=rec['heading'],
                            lat=rec['lat'], lon=rec['lon'], runway_area=rec['runway_area'],
                                runway_area_poly=rec['runway_area_poly'], runway_points=runway_points)

            runways.append(runway)


        return runways
    else:
        return None
    

class AirportDailyEvents(object):
    """
    Code for manipulating information about AirportDailyEventss (the original source
    of PlaneReports)
    """

    airport = ""          # ICAO code of airport
    type_of_event = ""
    hex = None
    flight = ""
    type_of_event = ""
    event_time = 0

    def __init__(self, **kwargs):
        for keyword in ["airport", "hex", "flight", "type_of_event", "event_time", "runway"]:
            setattr(self, keyword, kwargs[keyword])

#	def __str__(self):
#	fields = ['  {}: {}'.format(k,v) for k,v in self.__dict__.iteritems()
#			if not k.startswith("_")]
#		return "{}(\n{})".format(self.__class__.__name__, '\n'.join(fields))

    def to_JSON(self):
        """Return a string containing a JSON representation of a AirportDailyEvents"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, \
                          separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None):
        """
        Place an instance of a AirportDailyEvents into the DB - contains hex,
        type of event, flight, airport and seconds since epoch.

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        params = [self.airport, self.hex, self.flight, self.type_of_event, self.event_time, self.runway]
        sql = '''
			INSERT into airport_daily_events (airport, hex, flight, type_of_event, event_epoch, runway)
			VALUES (%s, %s, %s, %s, %s, %s);'''
        if printQuery:
            print(cur.mogrify(sql, params))
        try:
            cur.execute(sql, params)
        except Exception as foo:
            print("Some error", foo)
        cur.close()

    def delFromDB(self, dbconn, printQuery=None):
        """
        Remove an instance of a AirportDailyEvents from the DB.

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        sql = "DELETE from airport_daily_events WHERE airport like '%s' and hex like '%s' and event_epoch = %s" % (self.airport, self.hex, int(self.event_time))
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

def queryAirportDailyEvents(dbconn, myairport=None, myhex=None, myflight=None, printQuery=None,
                            myStartTime=None, myEndTime=None, myrunway=None):
    """
    Read an instance of a AirportDailyEvents record from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        myhex: One or more hex codes, separated by commas
        myflight: One or more flights, separated by commas
        myairport: One or more airports, separated by commas
        myStartTime: Look for events after this time
        myEndTime: Look for events before this time
        printQuery: Triggers printing the SQL query to stdout

    Returns:
        A psycopg2 cursor pointing to the results of the query
    """
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT airport, hex, flight, event_epoch, type_of_event
			FROM airport_daily_events'''

    conditions = 0

    if myStartTime or myEndTime or myflight or myhex or myflight or myairport:
        sql = sql + " where "

    if myStartTime:
        starttime = time.mktime(time.strptime(myStartTime, "%Y-%m-%d %H:%M:%S"))
        sql = sql + (" event_epoch >= %s " % int(starttime))
        conditions += 1
    if myEndTime:
        if conditions:
            sql = sql + " and "
        endtime = time.mktime(time.strptime(myEndTime, "%Y-%m-%d %H:%M:%S"))
        sql = sql + (" event_epoch <= %s " % int(endtime))
        conditions += 1

    if myhex:
        if conditions:
            sql = sql + " and "
        #
        # One or more hex codes
        #
        if myhex.find(',') != -1:
            numcommas = myhex.count(',')
            myhexs = myhex.split(',')
            sql = sql + " ("
            for i, xx in enumerate(myhexs):
                sql = sql + ("hex like '%s' " % xx)
                if i < numcommas:
                    sql = sql + " or "
            sql = sql + ")"
        else:
            sql = sql + (" hex like '%s'" % myhex)
        conditions += 1

    if myflight:
        if conditions:
            sql = sql + " and "
        #
        # we have to pad these with spaces out to 8 chars
        #
        if myflight.find(',') != -1:
            numcommas = myflight.count(',')
            myflights = myflight.split(',')
            sql = sql + " ("
            for i, ff in enumerate(myflights):
                sql = sql + ("flight like '%s' " % FLT_FMT.format(ff))
                if i < numcommas:
                    sql = sql + " or "
            sql = sql + ")"
        else:
            sql = sql + (" flight like '%s'" % FLT_FMT.format(myflight))

    if myairport:
        if conditions:
            sql = sql + " and "
        #
        # One or more ICAO airport codes
        #
        if myairport.find(',') != -1:
            numcommas = myairport.count(',')
            myairports = myairport.split(',')
            sql = sql + " ("
            for i, xx in enumerate(myairports):
                sql = sql + ("airport like '%s' " % xx)
                if i < numcommas:
                    sql = sql + " or "
            sql = sql + ")"
        else:
            sql = sql + (" airport like '%s'" % myairport)
        conditions += 1

    if myrunway:
        if conditions:
            sql = sql + " and "
        #
        # One or more runway names
        #
        if myairport.find(',') != -1:
            numcommas = myrunway.count(',')
            myrunways = myrunway.split(',')
            sql = sql + " ("
            for i, xx in enumerate(myrunways):
                sql = sql + ("runway like '%s' " % xx)
                if i < numcommas:
                    sql = sql + " or "
            sql = sql + ")"
        else:
            sql = sql + (" runway like '%s'" % myairport)
        conditions += 1

    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    return cur

def readAirportEventsDB(cur, numRecs=100):
    retlist = []
    data = cur.fetchmany(numRecs)
    daily_events = [AirportDailyEvents(**ev) for ev in data]
    for event in daily_events:
        retlist.append(event)
    return retlist


class DailyPlanesSeen(object):
    """
    Code for manipulating information about DailyPlanesSeen
    """

    date_seen = ""
    hex = None
    time_first_seen = 0
    time_last_seen = 0
    reporter = ""

    def __init__(self, **kwargs):
        for keyword in ["date_seen", "hex", "time_first_seen", "time_last_seen", "reporter"]:
            setattr(self, keyword, kwargs[keyword])

#	def __str__(self):
#	fields = ['  {}: {}'.format(k,v) for k,v in self.__dict__.iteritems()
#			if not k.startswith("_")]
#		return "{}(\n{})".format(self.__class__.__name__, '\n'.join(fields))

    def to_JSON(self):
        """Return a string containing a JSON representation of a DailyPlanesSeen"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, \
                          separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None):
        """
        Place an instance of a DailyPlanesSeen into the DB - contains name,
        type, location and URL for access

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        params = [self.date_seen, self.hex, self.time_first_seen, self.time_last_seen, self.reporter]
        sql = '''
			INSERT into daily_planes_seen (date_seen, hex, time_first_seen, time_last_seen, reporter)
			VALUES (%s, %s, %s, %s, %s);'''
        if printQuery:
            print(cur.mogrify(sql, params))
        try:
            cur.execute(sql, params)
        except Exception as err:
            print("Some exception as ", err)
        cur.close()

    def delFromDB(self, dbconn, printQuery=None):
        """
        Remove an instance of a DailyPlanesSeen from the DB.

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        sql = "DELETE from daily_planes_seen WHERE date_seen like '%s' and hex like %s and reporter like '%s'" % (self.date_seen, self.hex, self.reporter)
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

def readDailyPlanesSeen(dbconn, date, reporter, printQuery=None, numRecs=100):
    """
    Read instances of DailyPlanesSeen records from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        date: event date
        airport: ICAO code of airport
        printQuery: Triggers printing the SQL query to stdout

    Returns:
        A list of daily_planes_seen
    """
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT date_seen, hex, time_first_seen, time_last_seen, reporter
			FROM daily_planes_seen WHERE date_seen like \'%s\' and reporter like \'%s\'''' % (date, reporter)

    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    retlist = []
    data = cur.fetchmany(numRecs)
    daily_planes = [DailyPlanesSeen(**ev) for ev in data]
    for daily_plane in daily_planes:
        retlist.append(daily_plane)
    return retlist



class DailyFlightsSeen(object):
    """
    Code for manipulating information about DailyFlightsSeen
    """

    date_seen = ""
    hex = None
    time_first_seen = 0
    time_last_seen = 0
    reporter = ""

    def __init__(self, **kwargs):
        for keyword in ["date_seen", "flight", "time_first_seen", "time_last_seen", "reporter"]:
            setattr(self, keyword, kwargs[keyword])

#	def __str__(self):
#	fields = ['  {}: {}'.format(k,v) for k,v in self.__dict__.iteritems()
#			if not k.startswith("_")]
#		return "{}(\n{})".format(self.__class__.__name__, '\n'.join(fields))

    def to_JSON(self):
        """Return a string containing a JSON representation of a DailyFlightsSeen"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, \
                          separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None):
        """
        Place an instance of a DailyFlightsSeen into the DB - contains name,
        type, location and URL for access

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        params = [self.date_seen, self.flight, self.time_first_seen, self.time_last_seen, self.reporter]
        sql = '''
			INSERT into daily_flights_seen (date_seen, flight, time_first_seen, time_last_seen, reporter)
			VALUES (%s, %s, %s, %s, %s);'''
        if printQuery:
            print(cur.mogrify(sql, params))
        try:
            cur.execute(sql, params)
        except Exception as err:
            print("Error inserting ", err)
        cur.close()

    def delFromDB(self, dbconn, printQuery=None):
        """
        Remove an instance of a DailyFlightsSeen from the DB.

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        sql = "DELETE from daily_planes_seen WHERE date_seen like '%s' and flight like %s and reporter like '%s'" % (self.date_seen, self.flight, self.reporter)
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

def readDailyFlightsSeen(dbconn, date, reporter, printQuery=None, numRecs=100):
    """
    Read instances of DailyFlightsSeen records from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        date: event date
        airport: ICAO code of airport
        printQuery: Triggers printing the SQL query to stdout

    Returns:
        A list of daily_flights_seen
    """
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT date_seen, flight, time_first_seen, time_last_seen, reporter
			FROM daily_flights_seen WHERE date_seen like \'%s\' and reporter like \'%s\'''' % (date, reporter)

    if printQuery:
        print(cur.mogrify(sql))

    try:
        cur.execute(sql)
    except Exception as err:
        print("Error inserting ", err)

    retlist = []
    data = cur.fetchmany(numRecs)
    daily_flights = [DailyFlightsSeen(**ev) for ev in data]
    for daily_flight in daily_flights:
        retlist.append(daily_flight)
    return retlist




class DailyStats(object):
    """
    Code for manipulating information about DailyStats
    """
    record_date = ""
    max_dist = 0.0
    max_dist_hex = ""
    max_dist_flight = ""
    max_alt = 0.0
    number_reports = 0
    number_planes = 0
    max_time_epoch = 0

    def __init__(self, **kwargs):
        for keyword in ["record_date", "max_dist", "max_dist_hex", "max_dist_flight", "max_alt", "number_reports", "number_planes", "max_time_epoch", "reporter"]:
            setattr(self, keyword, kwargs[keyword])

#	def __str__(self):
#	fields = ['  {}: {}'.format(k,v) for k,v in self.__dict__.iteritems()
#			if not k.startswith("_")]
#		return "{}(\n{})".format(self.__class__.__name__, '\n'.join(fields))

    def to_JSON(self):
        """Return a string containing a JSON representation of a DailyStats"""
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, \
                          separators=(',', ':'))

    def logToDB(self, dbconn, printQuery=None):
        """
        Place an instance of a DailyStats into the DB - contains name,
        type, location and URL for access

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        params = [self.record_date, self.max_dist, self.max_dist_hex, self.max_dist_flight, self.max_alt, self.number_reports, self.number_planes, self.max_time_epoch, self.reporter]
        sql = '''
			INSERT into daily_stats (record_date, max_dist, max_dist_hex, max_dist_flight, max_alt, number_reports, number_planes, max_time_epoch, reporter)
			VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);'''
        if printQuery:
            print(cur.mogrify(sql, params))
        cur.execute(sql, params)
        cur.close()

    def delFromDB(self, dbconn, printQuery=None):
        """
        Remove an instance of a DailyStats from the DB.

        Args:
            dbconn: A psycopg2 DB connection
            printQuery: Triggers printing of constructed query (optional)

        Returns:
            Nothing much

        Raises:
            psycopg2 exceptions
        """
        cur = dbconn.cursor()
        sql = "DELETE from daily_stats WHERE record_date like '%s' and reporter like '%s'" % \
              (self.record_date, self.reporter)
        if printQuery:
            print(cur.mogrify(sql))
        cur.execute(sql)

def readDailyStats(dbconn, date="", reporter="", printQuery=None):
    """
    Read instances of DailyStats records from the DB.

    Args:
        dbconn: A psycopg2 DB connection
        date: event date
        airport: ICAO code of airport
        printQuery: Triggers printing the SQL query to stdout

    Returns:
        A list of daily_planes_seen
    """
    cur = dbconn.cursor(cursor_factory=RealDictCursor)
    sql = '''
		SELECT record_date, max_dist, max_dist_hex, max_dist_flight, max_alt, number_reports, number_planes, max_time_epoch, reporter
			FROM daily_stats WHERE record_date like \'%s\' and reporter like \'%s\'''' % date

    if printQuery:
        print(cur.mogrify(sql))
    cur.execute(sql)
    data = cur.fetchone()
    if data:
        daily_stats = DailyStats(**data)
        return daily_stats
    else:
        return None
