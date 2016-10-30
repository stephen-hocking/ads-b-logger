#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr
import matplotlib as mpl

parser = argparse.ArgumentParser(
    description="Plot plane positiions from a file")

parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to plot")
parser.add_argument('--lat', dest='latitude',
                    help="Latitude of plot centre - if not set will look for reporter in DB",
                    default=-35.343135, type=float)

parser.add_argument('--lon', dest='longitude',
                    help="Longitude of plot centre - if not set will look for reporter in DB",
                    default=149.141059, type=float)

parser.add_argument('-Y', '--y-dim', dest='ydim',
                    help="Y Dimension of plot in metres", default=850000, type=int)
parser.add_argument('-X', '--x-dim', dest='xdim',
                    help="X Dimension of plot in metres", default=850000, type=int)

parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot (otherwise auto-generated)", default=False)

parser.add_argument('--output-file', dest='outfile',
                    help="Output filename - if not specified, the plot is displayed directly.", default=False)

parser.add_argument('--autoscale', action="store_true",
                    dest='autoscale', default=False, help="Set area of plot to be 50kms larger than max distance of plane(s)")


args = parser.parse_args()

if args.outfile:
    mpl.use('Agg')
#
# Importing here, as they set the matplotlib backend to X if Agg call hasn't been made.
#
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap


if not args.latitude or not args.longitude:
    print("Require lat/lon cordinates")
    exit(1)

if not args.datafile:
    print("Need a data filename")
    exit(1)

xx, yy, lats, lons = [], [], [], []

reporter = pr.Reporter(name="", type="", lon=args.longitude, lat=args.latitude,
                       location="", url="", mytype="")

max_dist = 0.0

inputfile = pr.openFile(args.datafile)
data = pr.readFromFile(inputfile)

while data:
    for plane in data:
        xx.append(plane.lon)
        yy.append(plane.lat)
        zz = plane.distance(reporter)
        if zz > max_dist:
            max_dist = zz

    data = pr.readFromFile(inputfile)

if args.autoscale:
    args.xdim = args.ydim = max_dist * 2 + 50000

if args.debug:
    print("Height", args.height, "Width", args.width)

mymap = Basemap(width=args.xdim, height=args.ydim, resolution='h', projection='tmerc', \
              lat_0=args.latitude, lon_0=args.longitude)

lons,lats = mymap(xx, yy)


if args.debug:
    print("maximum distance", max_dist)
    
            
#mymap.drawmapboundary(fill_color='aqua')
#mymap.fillcontinents(color='#ddaa66',lake_color='aqua')
#mmyap.drawrivers()
#mymap.etopo()

fig = plt.figure(figsize=(10,10))
ax = plt.subplot(1,1,1)
mymap.shadedrelief()
mymap.drawstates()
mymap.drawcoastlines()

ax.scatter(lons, lats, marker='.', s=1, color='red')


if args.title:
    ax.set_title(args.title, fontsize=20)

if args.outfile:
    plt.savefig(args.outfile)
else:
    plt.show()
