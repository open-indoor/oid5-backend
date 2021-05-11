#!/usr/bin/python3

from bs4 import BeautifulSoup
from urllib.request import Request, urlopen, urlretrieve
import json
import re
import subprocess
import os
import psycopg2  # (if it is postgres/postgis)
from time import sleep 

# Get the page on which downloadable files are on according to regions.json data
with open('./regions.json') as regionsFile:
        data = json.load(regionsFile)
        regionsData = data["regions"][0]
        url = regionsData["html_page"]
# requester
req = Request(url)
# Page openning
html_page = urlopen(req)

soup = BeautifulSoup(html_page, "html.parser")

links_tmp = []
links = []

# Fill links_tmp with all links on the page defined 
for link in soup.findAll('a'):
        links_tmp.append(link.get('href'))

# Sort array links_tmp in links (keep only osm.pbf links)
for link in links_tmp:
    if link.endswith("osm.pbf") and "/" in link: #maybe uselatest
        links.append(link)
# Download data fom links array to downloadDest directory if empty

linksPart = []
linksPart.append(links[5])
# downloadDest = "/home/basile/oid5-backend/places-finder/testdata/"
baseDir = "/getdatadir/"
endDirtmp = linksPart[0].split("/")[:-1]
endDir = ""
for i in endDirtmp:
        endDir += i
downloadDest = baseDir + endDir
# dir creation
if not os.path.exists(downloadDest):
        os.makedirs(downloadDest, exist_ok=True)
#downlad data 
if len(os.listdir(downloadDest) ) == 0:
        for link in linksPart:
                urlretrieve("http://download.geofabrik.de/europe/" + link, downloadDest + link[len(endDir):])

# Convert all downloaded osm.pbf file to geojson file in order to fix geometry issues and import them in the postgis database
print(linksPart)
convertedFiles = []
print("Download in progress...")
for i in range(len(linksPart)):
        process = subprocess.run(["ogr2ogr","-f","GeoJSON", downloadDest + linksPart[i][len(endDir):-7] + "geojson",downloadDest + linksPart[i][len(endDir):], "multipolygons" ])
        # osmium extract bbox 47.394144,0.68484,47.404144,0.69484 -o output ville jean.osm.pbf http://download.geofabrik.de/europe/france/bretagne-latest.osm.pbf
        processDB = subprocess.run(["ogr2ogr","-f","PostgreSQL", "PG:dbname=openindoor-db host=openindoor-db port=5432 user=openindoor-db-admin password=admin123",downloadDest + linksPart[i][len(endDir):-7] + "geojson", "-nln", "regions" , "-overwrite", "-append", "-update", "-nlt", "MULTIPOLYGON"])
        # Prod -> Gerer la connexion string différement (env)
print(convertedFiles)
os.listdir(downloadDest)


