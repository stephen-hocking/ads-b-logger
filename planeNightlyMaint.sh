#! /bin/sh
#
# Sanitise yesterdays reports
#
PATH=$PATH:/usr/local/bin
YESTERDAY=`date -d yesterday +%F`
YESTERDAY_START="$YESTERDAY 00:00:00"
YESTERDAY_END="$YESTERDAY 23:59:59"
BKPDIR=~/PlaneReportLogBkps
#
# Backup yesterday
#
planedbreader.py -y /usr/local/lib/planelogger/dbconfig.yaml -t "$YESTERDAY_START"  -T "$YESTERDAY_END" | gzip -9 >  $BKPDIR/PlaneReportBkp-${YESTERDAY}.gz

planedbclean.py -y /usr/local/lib/planelogger/dbconfig.yaml

#
# Deduplication is taking up to 8 hours - leave it be for the time being
#
#numdel=`planededuplicate.py -y /usr/local/lib/planelogger/dbconfig.yaml | awk '{print $3}'`
#while [ $numdel -gt 0 ] && [ $? -eq 0 ]
#do
#  numdel=`planededuplicate.py -y /usr/local/lib/planelogger/dbconfig.yaml | awk '{print $3}'`
#done
