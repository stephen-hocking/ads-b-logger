#! /usr/bin/env python3
#
#
import time
import argparse
import PlaneReport as pr
import matplotlib as mpl

parser = argparse.ArgumentParser(
    description="Plot various attributes of plane reports")

parser.add_argument('--debug', action="store_true",
                    dest='debug', default=False, help="Turn on debug mode")
parser.add_argument('-f', '--file', dest='datafile',
                    help="A file to load data from to plot")

parser.add_argument('-t', '--title', dest='title',
                    help="Title of plot (otherwise auto-generated)", default=False)

parser.add_argument('--output-file', dest='outfile',
                    help="Output filename - if not specified, the plot is displayed directly.", default=False)

parser.add_argument('-a', '--attrs', dest='attrs', help="A comma seperated list of attributes to be plotted.", default='speed');

parser.add_argument('--lat', dest='latitude',
                    help="Latitude of point to calculate distance from.",
                    type=float)

parser.add_argument('--lon', dest='longitude',
                    help="Longitude of point to calculate distance from.",
                    type=float)

args = parser.parse_args()


if args.outfile:
    mpl.use('Agg')
#
# Importing here, as they set the matplotlib backend to X if Agg call hasn't been made.
#
import matplotlib.pyplot as plt


if not args.datafile:
    print("Need a data filename")
    exit(1)

xx, yy  = [], []

attrs = args.attrs.split(',')
zz={}
for i in attrs:
    zz[i] = []

if 'distance' in attrs and (not args.latitude or not args.longitude):
    print("Need location(lat, lon) to calculate distance")
    exit(1)

inputfile = pr.openFile(args.datafile)
data = pr.readFromFile(inputfile)
time_start = data[0].time
while data:
    for plane in data:
        xx.append(plane.time - time_start)
        for i in attrs:
            if i == 'distance':
                zz[i].append(pr.haversine(plane.lon, plane.lat, args.longitude, args.latitude) / 1000.0)
            else:
                zz[i].append(getattr(plane, i))

    data = pr.readFromFile(inputfile)
time_end = xx[-1] + time_start

start_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_start))
end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_end))
print(start_time_str, " ", time_start, " ", end_time_str, " ", time_end)

pltndx = 1
fig = plt.figure(figsize=(10,10))
if not args.title:
    args.title = start_time_str + " to " + end_time_str

fig.suptitle(args.title, fontsize=14, fontweight='bold')

for i in attrs:
    ax = fig.add_subplot(len(attrs), 1, pltndx)
    ax.plot(xx,zz[i], ',')
    ax.set_title(i)
    pltndx += 1


if args.outfile:
    plt.savefig(args.outfile)
else:
    plt.show()
