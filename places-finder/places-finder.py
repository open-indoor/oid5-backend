#!/usr/bin/python3

import requests
import sys
import json
import math
import uuid
import subprocess
import geopandas
from shapely.geometry import Polygon, Point, mapping
import fiona
import random
import os.path
import os
import glob
from shapely.geometry.multipolygon import MultiPolygon
import wget
from datetime import datetime

def deg2num(lon_deg, lat_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)


def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lon_deg, lat_deg)


def splitter(
        input_pbf="/data/tmp/europe_france_bretagne/building_indoor.osm.pbf",
        max_zoom = 18,
        bbox={"zoom": 1, "xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1},
        region_name="europe_france_bretagne"
    ):

    extracts = []
    my_finders = []
    tile_name = str(bbox["zoom"]) + "_" + str(bbox["xmin"]) + "_" + str(bbox["ymin"]) + "_" + str(bbox["xmax"]) + "_" + str(bbox["ymax"])
    for x in range(bbox["xmin"], bbox["xmax"] + 1):
        for y in range(bbox["ymin"], bbox["ymax"] + 1):
            (lon0, lat0) = num2deg(x, y, bbox["zoom"])
            (lon1, lat1) = num2deg(x+1, y+1, bbox["zoom"])
            sub_tile_name = str(bbox["zoom"]) + "_" + str(x) + "_" + str(y) + "_" + str(x + 1) + "_" + str(y + 1)
            filename = "/data/tmp/" + region_name + "/" + sub_tile_name + ".osm.pbf"
            print("Will generate: " + filename)
            # print("setting file: " + filename)
            extracts.append({
                "output": filename,
                "output_format": "pbf",
                "bbox": [lon0, lat0, lon1, lat1]
            })
            my_finders.append({
                "input_pbf": filename,
                "bbox": {
                    "zoom": bbox["zoom"] + 1,
                    "xmin": x * 2, "ymin": y * 2,
                    "xmax": (2*x) + 1, "ymax": (2*y) + 1
                }
            })
    conf = '/data/tmp/' + region_name + '/config' + "_"  + tile_name + '.json'
    print("conf:" + conf)
    with open(conf, 'w') as outfile:
        json.dump({"extracts": extracts}, outfile)
        outfile.flush()
        cmd = [
            "osmium", "extract",
            "--strategy=smart",
            "--overwrite",
            "--progress",
            "--config=" + conf,
            input_pbf
        ]

        print("cmd: " + str(cmd))
        indoor_filter = subprocess.run(cmd)

        print(glob.glob("/data/tmp/*.osm.pbf"))
        for my_finder in my_finders:
            print("Analyse: " + my_finder["input_pbf"])
            if os.path.getsize(my_finder["input_pbf"]) > 100000 and bbox["zoom"] < max_zoom:
                splitter(
                    input_pbf=my_finder["input_pbf"],
                    max_zoom=max_zoom,
                    region_name=region_name,
                    bbox=my_finder["bbox"]
                )
                os.remove(my_finder["input_pbf"])
            elif os.path.getsize(my_finder["input_pbf"]) < 75:
                os.remove(my_finder["input_pbf"])

def pbf_extractor(region):
    region_name=region["name"]
    region_poly=region["poly"]
    region_pbf=region["pbf"]
    poly_file = "/data/" + region_name + ".poly"
    pbf_file = "/data/" + region_name + ".osm.pbf"
    if not os.path.isfile(poly_file):
        print("download: " + poly_file)
        wget.download(region_poly, poly_file)
    if not os.path.isfile(pbf_file):
        print("download: " + region_pbf)
        wget.download(region_pbf, pbf_file)

    now = datetime.now()
    dt_string = now.strftime("%Y%m%d_%H%M%S")


    cmd = [
        "osmupdate",
        pbf_file,
        dt_string + "_" + pbf_file,
        "-B=" + poly_file
    ]
    print(cmd)
    building_indoor_filter = subprocess.run(cmd)

    os.makedirs("/data/tmp/" + region_name, exist_ok=True)
    building_indoor_pbf = "/data/tmp/" + region_name + "/building_indoor.osm.pbf"
    cmd = [
        "osmium",
        "tags-filter",
        "--progress",
        "--overwrite",
        "--output-format=pbf",
        "--output=" + building_indoor_pbf,
        "" + pbf_file,
        "w/indoor w/building:levels"
    ]
    building_indoor_filter = subprocess.run(cmd)
    splitter(
        input_pbf=building_indoor_pbf,
        max_zoom=18,
        region_name=region_name,
        bbox={
            "zoom": 1,
            "xmin": 0, "ymin": 0,
            "xmax": 1, "ymax": 1,
        }
    )

def main():
    print("coucou")
    with open('regions.json') as regions:
        region_data = json.load(regions)
    for region in region_data['regions']:
        pbf_extractor(region)

if __name__ == "__main__":
    main()

