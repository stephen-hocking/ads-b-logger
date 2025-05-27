#! /bin/sh
#
# Sanitise yesterdays reports
#
# Assumes a .pgpass file has been setup correctly for the user that will be running this cron job,
# and that that postgresql.conf has been altered so that the listen parameter includes
# the appropriate interfaces, and pg_hba.conf has allowed md5 password access for the 
# planereportupdater user.
#
PATH=$PATH:/usr/local/bin
YESTERDAY=`date -d yesterday +%F`
YESTERDAY_START="$YESTERDAY 00:00:00"
YESTERDAY_END="$YESTERDAY 23:59:59"
MONTH_AGO=`date -d "-2 month" +%Y-%m-%d`
MONTH_AGO_EPOCH=`date -d $MONTH_AGO +%s`
UTC_MONTH_AGO=`date -d @$MONTH_AGO_EPOCH -u "+%Y-%m-%d %H:%M:%S"`
DBHOST=192.168.251.1
DBUSER=planereportupdater

BKPDIR=~/PlaneReportLogBkps
#
# Backup yesterday
#
planedbreader.py -y /usr/local/lib/planelogger/dbconfig.yaml -t "$YESTERDAY_START"  -T "$YESTERDAY_END" | gzip -9 >  $BKPDIR/PlaneReportBkp-${YESTERDAY}.gz

#
# Clean up any dud data that may've escaped the logger checks
#
planedbclean.py -y /usr/local/lib/planelogger/dbconfig.yaml
#
# Clean out data older than a month
#
#psql -U $DBUSER -d PlaneReports -w -h $DBHOST -w --command="select count(*) from planreports where report_timestamp < '$UTC_MONTH_AGO';"

#
# Deduplication is taking up to 8 hours - leave it be for the time being
#
#numdel=`planededuplicate.py -y /usr/local/lib/planelogger/dbconfig.yaml | awk '{print $3}'`
#while [ $numdel -gt 0 ] && [ $? -eq 0 ]
#do
#  numdel=`planededuplicate.py -y /usr/local/lib/planelogger/dbconfig.yaml | awk '{print $3}'`
#done
