#!/bin/sh
# wait-for-postgres.sh

set -e
  
host="$1"
shift
args="$@"
  
until [curl $host -I | head -n 1 | cut -d$' ' -f2 = 200] ; do
  >&2 echo "Tegolas is unavailable - sleeping"
  sleep 3
done
  
>&2 echo "Tegola - executing command"
exec $args

