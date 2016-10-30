
# PlaneReport - Logging ADS-B data to a PostGIS DB and Analysing It

## Introduction

This is a suite of python & shell scripts that are used to log plane data from a running dump1090 instance, 
and place into a database that is equipped with Geographics Information System extensions. This allows interesting
queries to be made on the data. There also programs that make plots and animations of the flight data in both 2 and 3
dimensions.

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

There were a couple of problems - on a decent size amount of data, it took 20 minutes to run and producted an onscreen
animation last only lasted a couple of minutes. There wasn't any facilities to save the output as a movie. So I started
looking at the code to see if I could possibly find out what was going on. This gave me an excuse to start learning
Python.

The examination of a plotting program quickly got out of hand. I found a simpler & neater way of parsiing the JSON
objects that made up the list of planes returned by dump1090 (by using python's json library) and then wished I could do
other things with the data. At the time, I was working at Geosciences Australia, who, among many other interesting
things, do a lot of mapping work, and, as I found out, are heavy users of PostGIS, the GIS extensions to the
Postgres database. I had initially though of using MySQL, but its geometry data types and calculations used planar
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

## Database Description.

## Airports, and creating entries for them

## Reporters - what they are.

## Program Descriptions.

## Example Data files.
