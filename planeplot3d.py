#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr
from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
from  matplotlib.animation import FuncAnimation
from datetime import datetime
import time
import numpy as np


parser = argparse.ArgumentParser(
    description="Plot a movie of plane positiions from a file")

parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to plot")
parser.add_argument('--lat', dest='latitude',
                    help="Latitude of plot centre - if not set will look for reporter in DB", type=float)

parser.add_argument('--lon', dest='longitude',
                    help="Longitude of plot centre - if not set will look for reporter in DB", type=float)

parser.add_argument('-Y', '--y-dim', dest='ydim',
                    help="Y dimension of plot in metres", default=850000, type=int)
parser.add_argument('-X', '--x-dim', dest='xdim',
                    help="X dimension of plot in metres", default=850000, type=int)

parser.add_argument('--autoscale', action="store_true",
                    dest='autoscale', default=False, help="Set area of plot to be 50kms larger than max distance of plane(s)")

parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot", default=False)

parser.add_argument('--output-file', dest='outfile', help="Name of output animation file",
                    default=None)

parser.add_argument('--fps', dest='fps',
                    help="Frames per second of output movie (default=25)", default=25, type=int)
parser.add_argument('--codec', dest='codec',
                    help="FFMpeg codec used to create movie (default h264)", default='h264')


args = parser.parse_args()

if not args.latitude or not args.longitude:
    print("Require lat/lon cordinates")
    exit(1)

if not args.datafile:
    print("Need a data filename")
    exit(1)

xx, yy, lats, lons, alts = [], [], [], [], []
max_dist = 0.0

reporter = pr.Reporter(name="", type="", lon=args.longitude, lat=args.latitude,
                       location="", url="", mytype="")

inputfile = pr.openFile(args.datafile)
data = pr.readFromFile(inputfile)
while data:
    for plane in data:
        xx.append(plane.lon)
        yy.append(plane.lat)
        alts.append(int(plane.altitude))
        zz = plane.distance(reporter)
        if zz > max_dist:
            max_dist = zz
        
    data = pr.readFromFile(inputfile)

if args.debug:
    print("Arrays built")

if args.autoscale:
    args.xdim = args.ydim = (2 * max_dist) + 50

mymap = Basemap(width=args.xdim, height=args.ydim, resolution='h', projection='tmerc', \
                lat_0=args.latitude, lon_0=args.longitude)

lons,lats = mymap(xx, yy)

fig = plt.figure(figsize=(10,10))
#ax = Axes3D(fig)
ax = fig.add_subplot(111, projection='3d')
ax.plot(lons, lats, alts, ',', color='red')
#ax.view_init(azim=40, elev=20000)
#ax.scatter(lons, lats, alts, marker='.', color='red', s=1)
ax.add_collection3d(mymap.drawcoastlines())
ax.add_collection3d(mymap.drawstates())
if args.title:
    ax.set_title(args.title)
ax.set_zlabel('Altitude (m)')
ax.grid(True)
plt.draw()
if args.debug:
    print("showing plot")
plt.show()
