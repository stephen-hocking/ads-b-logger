#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr
from googleearthplot import googleearthplot


parser = argparse.ArgumentParser(
    description="Plot plane positiions from a file to kml")

parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")

parser.add_argument('--movie', action="store_true",
                    dest='movie', default=False, help="Save as a movie")

parser.add_argument('--timestretch', dest='timestretch', type=float,
                    help="Factor to adjust the elapsed time by.", default=0.1)

parser.add_argument('--camera-angle', dest='cameraAngle', type=float,
                    help="Number of degrees from vertical.", default=90.0)

parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to plot")

parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot (otherwise auto-generated)", default="")

parser.add_argument('--output-file', dest='outfile',
                    help="Output filename - if not specified, the plot is displayed directly.", default=False)


args = parser.parse_args()

if not args.datafile:
    print("Need a data filename")
    exit(1)

if not args.outfile:
    print("Need an output filename")
    exit(1)

xx, yy, zz, bearings, timedeltas = [], [], [], [], []
lastpos = ""
lasttime = -1

inputfile = pr.openFile(args.datafile)
data = pr.readFromFile(inputfile)

while data:
    for plane in data:
        if plane.report_location != lastpos:
            lastpos = plane.report_location
            if lasttime == -1:
                lasttime = plane.time - 1
            if (plane.time - lasttime) > 0:
                xx.append(plane.lon)
                yy.append(plane.lat)
                zz.append(plane.altitude)
                bearings.append(plane.track)
                timedeltas.append(plane.time - lasttime)
                lasttime = plane.time
            

    data = pr.readFromFile(inputfile)

if args.debug:
    print("Lons", xx)
    print("Lats", yy)
    print("Alts", zz)
    print("Bearings", bearings)
    print("Timedeltas", timedeltas)

mykmlplot = googleearthplot.googleearthplot()

if args.movie:
    mykmlplot.PlotPlaneMovie(yy, xx, zz, bearings, timedeltas, name=args.title, timestretch=args.timestretch, tilt=args.cameraAngle)
else:
    mykmlplot.PlotLineChart(yy, xx, heightList=zz, color="aqua", altMode='absolute', name=args.title, width=2)

mykmlplot.GenerateKMLFile(filepath=args.outfile)
