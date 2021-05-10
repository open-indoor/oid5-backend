#!/usr/bin/python3

from bs4 import BeautifulSoup
from urllib.request import Request, urlopen, urlretrieve
import json
import re
import subprocess
import os
import psycopg2  # (if it is postgres/postgis)
from time import sleep 
from flask import Flask

import requests

# Get the page on which downloadable files are on according to regions.json data        



def getLinks(html_page):
        links_tmp = []
        links = []
        # Fill links_tmp with all links on the page defined 
        soup = BeautifulSoup(html_page, "html.parser")
        for link in soup.findAll('a'):
                links_tmp.append(link.get('href'))

        # Sort array links_tmp in links (keep only osm.pbf links)
        for link in links_tmp:
                if link.endswith("osm.pbf") and "/" in link: #maybe uselatest
                        links.append(link)
        return links

# Download data fom links array to downloadDest directory if empty
def downladData(links):
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
        # Convert all downloaded osm.pbf file to geojson file in order to fix geometry issues
        convertedFiles = []
        print("Download in progress...")
        # add data to postgis db
        for i in range(len(linksPart)):
                process = subprocess.run(["ogr2ogr","-f","GeoJSON", downloadDest + linksPart[i][len(endDir):-7] + "geojson",downloadDest + linksPart[i][len(endDir):], "multipolygons" ])
                processDB = subprocess.run(["ogr2ogr","-f","PostgreSQL", "PG:dbname=db-postgis host=10.0.0.2 port=3306 user=postgres password=postgres",downloadDest + linksPart[i][len(endDir):-7] + "geojson", "-nln", "regions" , "-overwrite", "-append", "-update", "-nlt", "MULTIPOLYGON"])
                # processDB = subprocess.run(["ogr2ogr","-f","PostgreSQL", "PG:dbname=openindoor-db host=openindoor-db port=5432 user=openindoor-db-admin password=admin123",downloadDest + linksPart[i][len(endDir):-7] + "geojson", "-nln", "regions" , "-overwrite", "-append", "-update", "-nlt", "MULTIPOLYGON"])
        return os.listdir(downloadDest)

# app = Flask(__name__)


def download():
        print("yo")
        with open('./regions.json') as regionsFile:
                data = json.load(regionsFile)
                regionsData = data["regions"][0]
                url = regionsData["html_page"]
        # requester
        r = requests.get(url)
    # Page openning
#     html_page = urlopen(r)
        # Page openning
        # html_page = urlopen(req)
        links = getLinks(r.text)
        dowloadDest = downladData(links)
        return dowloadDest

# @app.route("/")

if __name__ == "__main__":
        print("yo1")
        # port = int(os.environ.get("PORT",8000))
        download()
        # app.run(debug=True,host='0.0.0.0',port=port)

