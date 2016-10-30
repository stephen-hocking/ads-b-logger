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
                    help="Latitude of plot centre", default=-35.343135, type=float)

parser.add_argument('--lon', dest='longitude',
                    help="Longitude of plot centre", default=149.141059, type=float)

parser.add_argument('-s', '--seconds-per-frame', dest='sec_per_frame',
                    help="Number of seconds that each frame of the movie represents", default=60, type=int)

parser.add_argument('--codec', dest='codec',
                    help="FFMpeg codec used to create movie (default h264)", default='h264')

parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot (otherwise auto-generated)", default=False)

parser.add_argument('--output-file', dest='outfile', help="Name of output animation file",
                    default=None)

parser.add_argument('--fps', dest='fps',
                    help="Frames per second of output movie (default=25)", default=25, type=int)

parser.add_argument('--display-hex', action="store_true",
                    dest='display_hex', default=False, help="Display the ICAO24 hex code for the planes")

parser.add_argument('--display-flight', action="store_true",
                    dest='display_flt', default=False, help="Display the Flight Number for the planes")

parser.add_argument('-r', '--rotate', action="store_true",
                    dest='rotate', default=False, help="Rotate the animation")

parser.add_argument('-Y', '--y-dim', dest='ydim',
                    help="Y dimension of of plot in metres", default=850000, type=int)
parser.add_argument('-X', '--x-dim', dest='xdim',
                    help="X dimension of plot in metres", default=850000, type=int)
parser.add_argument('-Z', '--z-dim', dest='zdim',
                    help="Z dimension of plot in metres", default=15000, type=int)

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
from mpl_toolkits.mplot3d import Axes3D
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from  matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d.art3d import juggle_axes


MAPX = 850000
MAPY = 850000

lats, lons, alts = [], [], []
drawableslst = []
annolist = []

time_slices = []
time_slices.append([])
time_slc_idx = 0
max_dist = 0.0
max_alt = 0.0

reporter = pr.Reporter(name="", type="", lon=args.longitude, lat=args.latitude, location="", url="", mytype="")

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
        if plane.altitude > max_alt:
            max_alt = plane.altitude
        
    data = pr.readFromFile(inputfile)

if args.debug:
    print("Number of slices is ", time_slc_idx)

diff_time = time_slices[-1][-1].time - time_slices[0][0].time

if args.debug:
    print("Begin time", time_slices[0][0].time, "end time", time_slices[-1][-1].time, "diff",
          diff_time, "calc slices", diff_time / args.sec_per_frame)

if args.autoscale:
    args.xdim = args.ydim = max_dist * 2 + 50000
    args.zdim = max_alt + 500

if args.debug:
    print("Max dist", max_dist, "Width", args.xdim, "Height", args.ydim)

mymap = Basemap(width=args.xdim, height=args.ydim, resolution='h', projection='tmerc', \
              lat_0=lat, lon_0=lon)

fig = plt.figure(figsize=(10,10))

#ax = p3.Axes3D(fig)
ax = fig.add_subplot(111, projection='3d')
ax.set_zlim3d([0, args.zdim])
if not args.title:
    plot_title = "Flights between " + time.strftime("%F %H:%M:%S", time.localtime(time_slices[0][0].time)) + \
                 " and " + time.strftime("%F %H:%M:%S", time.localtime(time_slices[-1][-1].time))
else:
    plot_title = args.title
ax.set_title(plot_title)

ax.set_zlabel('Altitude (m)')
ax.add_collection3d(mymap.drawcoastlines())
ax.add_collection3d(mymap.drawstates())

for plane in time_slices[0]:
    lon,lat = mymap(plane.lon, plane.lat)
    lons.append(int(lon))
    lats.append(int(lat))
    alts.append(int(plane.altitude))

centrex,centrey = mymap(reporter.lon, reporter.lat)

#myplot, = ax.plot(lons, lats, alts, ',')
#scat = ax.scatter(lons, lats, alts, c='r',color='red', s=1, marker='.', animated=True)
scat = ax.scatter(lons, lats, alts, color='red', s=1, marker='.', animated=True)

time_text = ax.text(-args.xdim / 5, (args.ydim * 16) / 17, (args.zdim / 10) * 9, '', fontsize=20)

annolist.append(ax.text(0, 0, 0, '', fontsize=8))

def init():
    time_text.set_text("")
    scat._offsets3d = juggle_axes(lons, lats, alts, 'z')
    drawableslst = []
    drawableslst.append(scat)
    drawableslst.append(time_text)
    for i in annolist:
        drawableslst.append(i)
    return tuple(drawableslst)

#
# the 3D version of plots doesn't support scatter plot annotations, so we have to use text objects
# The tex objects don't seem to support having their position updated, so we have to create them
# anew each time, then destroy them the next frame.
def update(frame):
    indicesdict = {}
    alts = []
    lons = []
    lats = []
    global annolist
    i = 0

    for i, plane in enumerate(time_slices[frame]):
        lon,lat = mymap(plane.lon, plane.lat)
        lons.append(int(lon))
        lats.append(int(lat))
        alts.append(int(plane.altitude))
        indicesdict[plane.hex] = i


    time_text.set_text(time.strftime("%F %H:%M:%S", time.localtime(first_time + (frame * args.sec_per_frame))))
    #
    # Remove old texts from matplotlib's internal state
    #
    for anno in annolist:
        if anno:
            ax.texts.remove(anno)
            anno = None
            
    annolist = []

    if args.display_hex or args.display_flt:
        for lastpoint in indicesdict:
            plane = time_slices[frame][indicesdict[lastpoint]]
            if args.display_hex and args.display_flt:
                txt = plane.hex + "/" + plane.flight
            elif args.display_hex:
                txt = plane.hex
            else:
                txt = plane.flight
            x,y =  mymap(plane.lon, plane.lat)
            z = plane.altitude
            annolist.append(ax.text(x, y, z, txt, fontsize=8))

    scat._offsets3d = juggle_axes(lons, lats, alts, 'z')

    if args.rotate:
        ax.view_init(30, (frame + 270) % 360)
    drawableslst = []
    drawableslst.append(scat)
    drawableslst.append(time_text)
    for anno in annolist:
        if anno:
            drawableslst.append(anno)
    if args.debug:
        print (frame, time.strftime("%F %H:%M:%S", time.localtime(first_time + (frame * args.sec_per_frame))), len(time_slices[frame]), len(indicesdict), len(annolist), len(ax.texts))

    return tuple(drawableslst)


animation = FuncAnimation(fig, update, init_func=init, frames=time_slc_idx, interval=40, repeat=False, blit=True)

if args.outfile:
    animation.save(args.outfile, fps=args.fps, codec=args.codec)
else:
    plt.show()
