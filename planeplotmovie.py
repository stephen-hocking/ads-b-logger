#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr
import matplotlib as mpl
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
                    help="Latitude of plot centre - if not set will look for reporter in DB", default=-35.343135, type=float)

parser.add_argument('--lon', dest='longitude',
                    help="Longitude of plot centre - if not set will look for reporter in DB", default=149.141059, type=float)

parser.add_argument('-s', '--seconds-per-frame', dest='sec_per_frame',
                    help="Number of seconds that each frame of the movie represents", default=60, type=int)
parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot (otherwise auto-generated)", default=False)


parser.add_argument('--codec', dest='codec',
                    help="FFMpeg codec used to create movie (default h264)", default='h264')

parser.add_argument('--output-file', dest='outfile', help="Name of output animation file",
                    default=None)

parser.add_argument('--fps', dest='fps',
                    help="Frames per second of output movie (default=25)", default=25, type=int)

parser.add_argument('--display-hex', action="store_true",
                    dest='display_hex', default=False, help="Display the ICAO24 hex code for the planes")

parser.add_argument('--display-flight', action="store_true",
                    dest='display_flt', default=False, help="Display the Flight Number for the planes")

parser.add_argument('-Y', '--y-dim', dest='ydim',
                    help="Height of plot in metres", default=850000, type=int)
parser.add_argument('-X', '--x-dim', dest='xdim',
                    help="Width of plot in metres", default=850000, type=int)

parser.add_argument('--autoscale', action="store_true",
                    dest='autoscale', default=False, help="Set area of plot to be 50kms larger than max distance of plane(s)")

args = parser.parse_args()

if not args.latitude or not args.longitude:
    print("Require lat/lon cordinates")
    exit(1)
else:
    lat = float(args.latitude)
    lon = float(args.longitude)

if not args.datafile:
    print("Need a data filename")
    exit(1)

if args.outfile:
    mpl.use('Agg')

from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from  matplotlib.animation import FuncAnimation


lats, lons, times = [], [], []

time_slices = []
time_slices.append([])
time_slc_idx = 0
max_dist = 0.0

reporter = pr.Reporter(name="", type="", lon=args.longitude, lat=args.latitude, location="", url="")

inputfile = pr.openFile(args.datafile)
data = pr.readFromFile(inputfile)
if data:
    first_time = data[0].time
    next_time = first_time + args.sec_per_frame
while data:
    for plane in data:
        if plane.time >= next_time:
            # Catch case where there's a long time without action
            if plane.time > (next_time +  args.sec_per_frame):
                while next_time < plane.time:
                    time_slc_idx += 1
                    time_slices.append([])
                    next_time += args.sec_per_frame
            else:    
                time_slc_idx += 1
                time_slices.append([])
                next_time += args.sec_per_frame
        time_slices[time_slc_idx].append(plane)
        zz = plane.distance(reporter)
        if zz > max_dist:
            max_dist = zz
        
    data = pr.readFromFile(inputfile)

if args.debug:
    print("Number of slices is ", time_slc_idx)
    print("Max dist is", max_dist)

diff_time = time_slices[-1][-1].time - time_slices[0][0].time

if args.debug:
    print("Begin time", time_slices[0][0].time, "end time", time_slices[-1][-1].time, "diff",
          diff_time, "calc slices", diff_time / args.sec_per_frame)

fig = plt.figure(figsize=(10,10))
ax = plt.subplot(1,1,1)

if not args.title:
    plot_title = "Flights between " + time.strftime("%F %H:%M:%S", time.localtime(time_slices[0][0].time)) + \
                 " and " + time.strftime("%F %H:%M:%S", time.localtime(time_slices[-1][-1].time))
else:
    plot_title = args.title

ax.set_title(plot_title)

if args.autoscale:
    args.xdim = args.ydim = max_dist * 2 + 50000

mymap = Basemap(width=args.xdim, height=args.ydim, resolution='h', projection='tmerc', \
              lat_0=lat, lon_0=lon)

#mymap.drawmapboundary(fill_color='aqua')
#mymap.fillcontinents(color='#ddaa66',lake_color='aqua')
#mmyap.drawrivers()
#mymap.etopo()

mymap.shadedrelief()
mymap.drawstates()
mymap.drawcoastlines()

i = 0
positions = []
drawableslst = []
annolist = []

scat = ax.scatter(lons, lats, marker='.', color='red',  s=1)

time_text = ax.text(args.xdim / 3.4, -(args.ydim / 17), '', fontsize=20)

annolist.append(ax.annotate('', xy=(0, 0), xycoords='data', fontsize=8))

def init():
    scat.set_offsets([])
    time_text.set_text("")
    drawableslst = []
    drawableslst.append(scat)
    drawableslst.append(time_text)
    for i in annolist:
        drawableslst.append(i)
    return tuple(drawableslst)

def update(frame):
    positions = []
    indicesdict = {}
    i = 0

    for i, plane in enumerate(time_slices[frame]):
        lon,lat = mymap(plane.lon, plane.lat)
        positions.append((lon, lat))
        indicesdict[plane.hex] = i

    scat.set_offsets(positions)
    time_text.set_text(time.strftime("%F %H:%M:%S", time.localtime(first_time + (frame * args.sec_per_frame))))
    for anno in annolist:
        anno.set_text('')
        anno.set_position((0, 0))

    if args.display_hex or args.display_flt:
        if len(annolist) < len(indicesdict):
            z = len(indicesdict) - len(annolist)
            while z > 0:
                z -= 1
                annolist.append(ax.annotate('', xy=(0, 0), xycoords='data', fontsize=8))


        for i, lastpoint in enumerate(indicesdict):
            plane = time_slices[frame][indicesdict[lastpoint]]
            if args.display_hex and args.display_flt:
                txt = plane.hex + "/" + plane.flight
            elif args.display_hex:
                txt = plane.hex
            else:
                txt = plane.flight
            x,y =  mymap(plane.lon, plane.lat)
            annolist[i].set_text(txt)
            annolist[i].set_position((x, y))

    drawableslst = []
    drawableslst.append(scat)
    drawableslst.append(time_text)
    for i in annolist:
        drawableslst.append(i)
    if args.debug:
        print (frame, time.strftime("%F %H:%M:%S", time.localtime(first_time + (frame * args.sec_per_frame))), len(indicesdict))
    return tuple(drawableslst)


animation = FuncAnimation(fig, update, init_func=init, frames=time_slc_idx, interval=40, repeat=False, blit=True)

if args.outfile:
    animation.save(args.outfile, fps=args.fps, codec=args.codec)
else:
    plt.show()
