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
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to plot")

parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot (otherwise auto-generated)", default=False)

parser.add_argument('--output-file', dest='outfile',
                    help="Output filename - if not specified, the plot is displayed directly.", default=False)


args = parser.parse_args()

if not args.datafile:
    print("Need a data filename")
    exit(1)

if not args.outfile:
    print("Need an output filename")
    exit(1)

xx, yy, zz = [], [], []

inputfile = pr.openFile(args.datafile)
data = pr.readFromFile(inputfile)

lastpos = ""

while data:
    for plane in data:
        if plane.report_location != lastpos:
            lastpos = plane.report_location
            xx.append(plane.lon)
            yy.append(plane.lat)
            zz.append(plane.altitude)

    data = pr.readFromFile(inputfile)

if args.debug:
    print("Lons", xx)
    print("Lats", yy)
    print("Alts", zz)

mykmlplot = googleearthplot.googleearthplot()
mykmlplot.PlotLineChart(yy, xx, heightList=zz, name="trajectory2",color="aqua")
mykmlplot.GenerateKMLFile(filepath=args.outfile)
