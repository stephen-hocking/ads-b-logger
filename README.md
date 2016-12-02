
# PlaneReport - Logging ADS-B data to a PostGIS DB and Analysing It

## Introduction

This is a suite of python & shell scripts that are used to log plane data from a running dump1090 instance, 
and place into a database that is equipped with Geographics Information System extensions. This allows interesting
queries to be made on the data. There also programs that make plots and animations of the flight data in both 2 and 3
dimensions.


## Database Description.
The design is rather trivial, with the DB having tables describing the reports that come in, details about the entities doing the reporting, descriptions of airports, and various tables that hold statistics for each day.

### planereports
* hex - 6 character ICAO24 hexadecimal number that is the unique identifier for the aircraft issuing the report.
* squawk - unique 4 character code assigned to an aircraft by the local airtraffic controller. Can also be used to indicate emrgencies of various types.
* flight - The flight number the aircraft is travelling under at the moment, e.g. QFA423
* isMetric - boolean indication if measurements have been converted from feet/knots to metres/km/h.
* isMLAT - if report has been derived from collating measurements from various reports and using them to triangulate the aircraft's position, as some don't report their position. Requires reporters to be co-ordinated by a central authority.
* altitude - height of the aircraft above sealevel. The special value of '0' indicates that the "ground" flag was set by a version of dump1090 (dump1090-mutability) which is capable of decoding that signal. The original piaware code wasn't, but now does.
* speed - speed of the aircraft at that point in time.
* vert_rate - rate per minute of the aircraft's ascent/descent.
* bearing - direction of the aircraft's travel in degrees.
* messages_sent - how many messages the reporter has seen from this aircraft during this appearance.
* report_location - the position of the aircraft. Is translated between WKBF to lat/lon as required.
* report_epoch - time that this report was seen, in seconds since the epoch (1 Jan 1970)
* reporter - name of the reporter that logged this record.
* rssi - Received Signal Strength Indication - in dB, negative values. 0 means no recorded value. Readings start getting dodgy at around -25 for piaware stations. dump1090-mutability only.
* nucp - Navigational Uncertainity Category: Position. An indicator of how accurate the position reading might be, with values from 0 (terrible) to 9 (excellent). -1 used to indicate no value supplied. dump1090-mutability only.
* isgnd - boolean used to indicate if aircraft is on ground. Not all transponders seem to support this. dump1090-mutability only.

### reporter
* name - the name of the reporter
* type - the type. Not currently used at this point, it would be used to differentiate between various versions of dump1090.
* reporter_location - the geographic location of the reporter.
* url - the url used to query for any planereports from this reporter.

### airport
* icao - the 4 letter identifier of the airport registered with the ICAO
* iata - the 3 character name of the airport, as used by the IATA.
* name - the human usable name of the airport
* city - the city or town (if any) that is associated with this airport.
* country - the country that the airport is located in.
* altitude - the altitude of the airport in metres.
* location - the co-ordinates of the airport.
* runways - a polygon describing the airport's runways.

### `airport_daily_events`
* hex - the ICAO24 code of the aircraft in question
* flight - the flight number the plane was using at the time in question
* `type_of_event` - the event being one of landing, takeoff, or bump and go.
* airport - the 4 character ICAO code of the airport in question.
* event_epoch - the time of the event, expressed as numer of seconds since the epoch.

### `daily_flights_seen`
* date_seen - date when flight seen
* flight - the flight number of the aircraft.
* reporter - which reporter saw it.
* `time_first_seen` - when it was first seen, expressed ast seconds since the epoch
* `time_last_seen` - when it was last seen, expressed ast seconds since the epoch

### `daily_planes_seen`
* date_seen - date when flight seen
* hex - the ICAO24 identifier of the aircraft.
* reporter - which reporter saw it.
* `time_first_seen` - when it was first seen, expressed ast seconds since the epoch
* `time_last_seen` - when it was last seen, expressed ast seconds since the epoch

### daily_stats
* record_date - the date of these stats.
* max_dist - the maximum distance from a reporter recorded this day.
* `max_dist_hex` - the ICAO24 identifier of the plane that was furtherest away from a reporter.
* `max_dist_flight` - the flight number of the far aircraft.
* max_alt - the maximum altitude in metres seen during the day.
* number_reports - the number of reports seen today for this reporter.
* number_planes - number of different planes seen today for this reporter.
* `max_time_epoch` -  the time when the maximum distance was recorded.
* reporter - the name of the reporter that these stats are for today.
* `max_dist_loc` - the location of the report that was furtherest away.


## Airports, and creating entries for them
A small utility program `loadairport.py` exists to add an airport to the database or update its entry. The file format is straight forward, as follows:

            Line 1: 4 char ICAO code for airport
            Line 2: 3 char IATA code for airport
            Line 3: Airport name
            Line 4: Airport City
            Line 5: Airport Country
            Line 6: Airport Altitude (in metres)
            Line 7: cordinates (lat/lon)
            Lines 8-n: Polygon vertices enclosing runways only, not taxiways and parking

An example can be found in the file `canberra.airport`. The runway vertices in lat/lon format can be found by viewing the airport in google maps, zooming in, and clicking on each corner of the runway. A lat/lon part with be display, which can be copied and pasted into an editor window.

An alternative method would be to write a program that can pull out the data from X-Plane's `apt.dat` file, which contains entries for most of the airports in the world.

## Reporters - what they are.
A reporter is usually a small raspberry pi running dump1090. They each should have a unique name, a location, a type, and a URL that allows JSON access to the internal data. A small utility program, `loadreporter.py`, inserts or updates the data into the database. Thne file format is simple, and is as follows:

            Line 1: Name of reporter (no more than 10 chars)
            Line 2: reporter type piaware or mutability, although this field isn't used by anything yet
            Line 3: Lat/lon of reporter location, comma separated.
            Line 4: URL to access the reporter, e.g. http://planereporter/dump1090/data/aircraft.json


## Program Descriptions.
There are a number of options common to most programs, which will be described first. A YAML file is used to describe how to access the database, and its format shall also be described.

### Common options
* `-y, --db-conf-file filename` - short & long form used to specify a YAML file to read DB connection arguments from. The YAML file has the following format:

```
adsb_logger:
  dbhost:  hostname or ip address
  dbuser:  planereportupdater
  dbpassword:  password
```

* `--debug` - set the debug flag, which, depending on the program, will print all sorts of useful information to see what it's doing and how it's querying the DB.
* `-t, --start-time "YYYY-MM-DD HH:MM:SS"` - the start of the time window from which the programs will utilise data.
* `-T, --end-time "YYYY-MM-DD HH:MM:SS"` - the end of the time window from which the program will process data.
* `-x, --hex hexcode[,hexcode2,hexcode3...]` - the ICAO24 hex codes of the aircraft we are interested in. One or more can be specified, separated by commas.
* `-f, --file filename` - Used by programs that read text files. when `filename` is a `-`, the program will read from standard input.
* `-f, --flights flight1[,flight2....]` - the flight numbers of the aircraft we are interested in, one or more can be specified, separated by commas.
* `-d, --min-distance nnnnn` - the minimum distance the aircraft have to be away, specified in metres.
* `-D, --max-distance nnnn` - The maximum distance the aircraft can be away, in metres.
* `-A, --max-altitude nnnn` - The aircraft have to be no higher than this, specified in metres.
* `-a, --min-altitude nnnnn` - The aircraft have to be no lower than this, specified in metres.
* `-n, --num-recs nnnnn` - the number of records to read at a time. Usually defaults to 100.
* `-r, --reporter name` - Specifies the name of the reporter. Defaults to "Home1"
* `-j, --json` - print output as JSON, rather than text.
* `-l, --log-to-db` - Log the discovered events to the DB.
* `-q, --quiet` - Don't print any text on the screen.


### Common plot options
* `--autoscale` - Used in plotting programs to autoscale the output so that the plotted positions fit comfortably withing the image.
* `--lat` -  Specifiy latitude of centre of plot
* `--lon` - Specify longitude of centre of plot
* `-t, --title string` - Title of plot or movie, auto generated if not otherwise specified.
* `-Y, --y-dim nnnn` - Y dimension of plotted area in metres.
* `-X, --x-dim nnnn` - X dimension of plotted area in metres.
* `-Z, --z-dim nnnn` - Z dimension of plotted area in metres

### Common movie options
* `-s, --seconds-per-frame nn` - The number of seconds of real time that each frame of the movie represents.
* `--fps` - Number of frames per second of output movie.
* `--codec codec` - specifies the FFMpeg codec used in creating movie files. Default is h264.
* `--display-hex` - Display the ICAO24 hex code of the plane(s) in the movies.
* `--display-flight` - Display the flight number of planes in the movies
* `--rotate` - Rotate the point of view in a 3D movie. Buggy - have to revise my basic highschool trig and get title positioning right.

### Programs and their options

#### planelogger.py
Used to acquire data form either a text file or a URL. The data can be printed to the standard output, or logged to a dataase. It uses the standard options, as well as the following:

* `-i, --sample-interval nnn` - Numer of seconds between each sample from a URL. Default is 1.
* `-c, --sample-count nnn` - Number of samples to collect (-1 for infinity)
* `-u, --url string` - the URL of the running dump1090 instance to get data from. E.g. "http://planes.example.com/data/aircraft.json"

#### planeairport.py
This program is used to print or log the events at an airport. The options are standard, except for the following:

* `-A, --airport name` - the name of the airport in which we're interested.
* `-a, --committed-height nnnn` - the height above the airport in metres, below which the aircraft is considered be interested in the airport, defaults to 200.


#### planedailyevents.py
Looks for all the aircraft and flights seen during the day, and logs them to a DB if required. Uses the standard option set, except as follows:

* `-x, --planes` - Look for planes.
* `-f, --flights` - Look for flights

#### planedailystats.py
This programs calculates the daily stats for a given reporter and day. It uses the standard options, sans the data filtering ones (min/max speed,alt,dist etc). Is still not complete,as writing it pointed out that some messages are corrupted in transmission, resulting in ludicrous speeds and altitudes. Addressing this corruption is an ongoing work.

#### planedbclean.py.
Largely superflous, as `planelogger.py` now applies some basic filters before storing the data. Uses the standard options.

#### planedbreader.py
Intended to provide input for various plotting programs, as well as JSON backups of planereport data that can be imported by `planelogger.py`.Uses the standard set of options, plus the following:

* `--min-rssi nnn` - Reports must have an RSSI value greater that or equal to this.
* `--max-rssi nnn` - Reports mus have an RSSI value less than or equal to this.
* `--min-nucp  nn` Reports must have an NUCP value greater than or equal to this.
* `--max-nucp  nn` Reports must have an NUCP value less than or equal to this.
* `--min-speed nn` - Reports must have a speed greater than or equal to this. Units km/h.
* `--max-speed nn` - Reports must have a speed less than or equal to this. Units km/h.




#### planededuplicate.py
Was intended to trim out all those instances of reports with the same position for a given plane. Put on hold for the time being until the data cleaning programs are sorted out. Uses the standard options.

#### planeplot.py
Can produce an on-screen plot from a data file, or will output to a PNG format file. Uses standard plot options.

#### planeplot3d.py
Can produce an on-screen plot from a data file, or will output to a PNG format file. Uses standard plot options. Can be used to examine a 3d view on the screen of a plane's path.

#### planeplotmovie.py
Uses standard plot and movie options.  Will provide a 2d plot of the plane reports that are fed to it. Output can be displayed on-screen or saved to a file.

#### planeplot3dmovie.py
Uses standard plot and movie options. Will provide a 3d movies of aircraft position reports.

#### plotattr.py
Is used to plot various attributes of planereports. More intended to be used to pick up correlations between various attributes. Can plot multiple attributes at once.

* `--lat nnn.nn` latitude of where the reports were taken. Intended for use in calculating distance.
* `--lon nnn.nn` longitude of where the reports were taken. Intended for use in calculating distance.
* `--attrs zz,xx,yy` - comma separated list of attributes to plot. A psuedo attribute, `distance` is also included to display the distance in km.
* `--title str` - The overall plot title, if specified. Will default to the start & end times of the data that's being plotted.


## Example Data files.
* `TEY.dat` - Data from a survey flight that was undertaken over the ACT in January 2016. People in the business tell me it's a very typical flight path, including the 2nd flight for post-survey calibration. 
* `PlaneReportBkp-2016-08-05.gz` - a compressed datafile including reports from a number of reporters on the 5th of August 2016, in Canberra and Sydney.

## Example plots and movies
* `TEY.png` - generated with `planeplot.py -f TEY.dat --autoscale --lat -35.34 --lon 149.14 --output-file TEY.png --title "Plots of flight TEY 2016-01-09"`
* `TEY-2D.mp4` - generated with `python3.4 planeplotmovie.py -f TEY.dat --autoscale --lat -35.34 --lon 149.14 --output-file TEY-2D.mp4 --display-flight --display-hex`
* `TEY-3D.mp4` - generated with `python3.4 planeplot3dmovie.py -f TEY.dat --autoscale --lat -35.34 --lon 149.14 --output-file TEY-3D.mp4 --display-flight --display-hex`
* `2016-08-05.png` - generated with `gunzip < PlaneReportBkp-2016-08-05.gz | python3.4 planeplot.py -f - --autoscale --lat -35.34 --lon 149.14 --output-file 2016-08-05.png --title "Plots for 2016-08-05"`
* `2016-08-05-2D.mp4` generated with `gunzip < PlaneReportBkp-2016-08-05.gz | python3.4 planeplotmovie.py -f - --autoscale --lat -35.34 --lon 149.14 --output-file 2016-08-05-2D.mp4 --display-flight --display-hex`
* `2016-08-05-3D.mp4` generated with `gunzip < PlaneReportBkp-2016-08-05.gz | python3.4 planeplot3dmovie.py -f - --autoscale --lat -35.34 --lon 149.14 --output-file 2016-08-05-3D.mp4 --display-flight --display-hex`


## Things to do...

### Some data glitches - how to correct?
The planereport data is weakly checksummed, which is not enough to correct or detect some errors. There are a number of ways to attempt to correct this.
* Use Kalman filters. We could correct altitude (using `vert_rate` and previous altitude measurements) and position (using `speed` and previous positions). If either `vert_rate` or `speed` are clobbered, then this is problematic.  I plan on using 1d smoothing (as described in http://scipy-cookbook.readthedocs.io/items/SignalSmooth.html) to sort out both `speed` and `vert_rate`, then use Kalman filtering to sort out `altitude` and `position`, as seen in http://scipy-cookbook.readthedocs.io/items/KalmanFiltering.html.
* Use quorum voting. Have a number of receivers picking up the same messages from the aircraft. They are then compared, and the majority vote on values (position, speed , altitude etc) wins. The suspect records are then deleted from the database. This will take some experimention with distance and placement of receivers.

### Jazzing up the 3D plots.
The 3D plots would benefit from 3D terrain. There are DEM (Digital Elevation Model) data sets around, methods of finding them and figuring out how to programatically extract the areas of interest need to be figured out, so they can then be transformed into npz data sets, so that code as described in http://matplotlib.org/examples/mplot3d/custom_shaded_3d_surface.html can be used.

### Write Puppet scripts to install & configure packages and DB
Not much else needs to be said - really need a way to simply and easily install the necessary packages, configure the DB so that it can be accessed remotely, and create the DB.

## History

The project started when I was messing around with Software Defined Radio and discovered that flightaware.com
had a ready-made Raspberry Pi image that had dump1090 pre-installed. After making my own antenna
(see http://www.atouk.com/wordpress/?page_id=237# for details) and discovering the hard way that
electronics outdoors really needed to be water-proofed, I was able to see the planes flying around nearby.

On the flightaware forums, I stumbled up someone who'd written some MatLab code (see
https://www.reddit.com/r/RTLSDR/comments/2ie6z6/3d_visualization_of_air_traffic_in_my_area_levc/? 
for the discussion and a link to output on imagur)to make a 3D plot of some of the data he'd collected. I bought a
student edition of matlab but discovered the mapping toolkit wasn't included and cost about 1400 AUD. Looking around
further, I discovered that someone else (see https://github.com/aarkebauer/dump1090plot for code) had done something
similar in python, and that introduced me to matplotlib.

There were a couple of problems - on a decent size amount of data, it took 20 minutes to run and produced an onscreen
animation last only lasted a couple of minutes. There wasn't any facilities to save the output as a movie. So I started
looking at the code to see if I could possibly find out what was going on. This gave me an excuse to start learning
Python.

The examination of a plotting program quickly got out of hand. The original author had been parsing the plane data using the regex library, which was rather slow. I found a simpler & neater way of parsing the JSON
objects returned by dump1090 (by using python's json library) and then wished I could do
other things with the data. At the time, I was working at Geosciences Australia, who, among many other interesting
things, do a lot of mapping work, and, as I found out, are heavy users of PostGIS, the GIS extensions to the
Postgres database. I had initially thought of using MySQL, but its geometry data types and calculations used planar
geometry, rather than the spheriodal class which gives more accurate results for work over a decent sized area.
So I learned me some Postgres/PostGIS.

At around this time Geosciences decided to re-organise and outsource large chunks of its IT department, so I, as a
contractor, shortly found myself with a lot of spare time on my hands. This gave me the opportunity to continue
learning about one of the mapping libraries within Python, Basemap, and how it fitted in with matplotlib. This gave me
an excuse to produce some nice plotting and animation programs, and to also see if I could work out what aircraft
were landing and taking off from the airport I could see from my balcony. This was attemped by crafting SQL queries that
determined what reports were made from within a polygon describing the runways, and processing the results.

I'm also writing reports that collect various stats for each day, and scripts that will generate plots and movies 
as part of a scheduled job stream.
