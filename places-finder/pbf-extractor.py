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
import numpy

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

# https://download.geofabrik.de/europe/france/bretagne-latest.osm.pbf


def splitter(
        my_uuid="",
        input_pbf="data/bretagne-latest.osm.pbf",
        zoom=1,
        max_zoom = 18,
        bbox={"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1},
        name="bretagne"
    ):
    # if (bbox.xmax - bbox.xmin) > 2 or bbox.ymax - bbox.ymin) > 2:
    #     splitter(
    #         input_pbf=input_pbf,
    #         zoom=zoom - 1,
    #         bbox={
    #             xmin: bbox.xmin / 2,
    #             ymin: bbox.ymin / 2,
    #             xmax: bbox.xmax / 2,
    #             ymax: bbox.ymax / 2,
    #         },
    #         name=name
    #     )
    #     return
    
    extracts = []
    my_finders = []
    for x in range(bbox["xmin"], bbox["xmax"] + 1):
        for y in range(bbox["ymin"], bbox["ymax"] + 1):
            (lon0, lat0) = num2deg(x, y, zoom)
            (lon1, lat1) = num2deg(x+1, y+1, zoom)
            filename = "/tmp/" \
                + name + "_" + str(zoom) + "_" \
                + str(x) + "_" + str(y) + "_" + str(x + 1) + "_" + str(y + 1) \
                + my_uuid + ".osm.pbf"
            # print("setting file: " + filename)
            extracts.append({
                "output": filename,
                "output_format": "pbf",
                "bbox": [lon0, lat0, lon1, lat1]
            })
            my_finders.append({
                "zoom": zoom + 1,
                "input_pbf": filename,
                "bbox": { "xmin": x * 2, "ymin": y * 2, "xmax": (2*x) + 1, "ymax": (2*y) + 1 }
            })
    conf = '/tmp/config' + my_uuid + '.json'
    print("conf:" + conf)
    # print(json.dumps(extracts, sort_keys=True, indent=4))
    with open(conf, 'w') as outfile:
        json.dump({"extracts": extracts}, outfile)
    cmd = "osmium extract " \
        + "--strategy=smart " \
        + "--overwrite " \
        + "--progress " \
        + "--config=" + conf + " " \
        + input_pbf
    # os.remove(input_pbf)

    print("cmd: " + cmd)
    indoor_filter = subprocess.run(
        cmd,
        shell=True
    )
    # indoor_filter.communicate()

    for my_finder in my_finders:
        if os.path.getsize(my_finder["input_pbf"]) > 100000 and zoom < max_zoom:
            splitter(
                my_uuid=my_uuid,
                input_pbf=my_finder["input_pbf"],
                zoom=my_finder["zoom"],
                max_zoom=max_zoom,
                name=name,
                bbox=my_finder["bbox"]
            )
            os.remove(my_finder["input_pbf"])
        elif os.path.getsize(my_finder["input_pbf"]) < 75:
            os.remove(my_finder["input_pbf"])

def finder(
    building_indoor_name="bretagne_building_indoor",
    my_uuid="_b3c217c6-bd01-4c03-b56c-6e53c6d90916",
    input_pbf="data/bretagne-latest.osm.pbf"
):
"""
Entrees :
building_indoor_name :
my_uuid :
input_pbf :
"""
    building_indoors = {"type": "FeatureCollection", "features": [
        {"type":"Feature","geometry":{
            "type":"MultiPolygon",
            "coordinates":[]
        }}
       ]
    }
    debug = {"type": "FeatureCollection", "features": []}
    for building_indoor_pbf in glob.glob('/tmp/' + building_indoor_name + '*' + my_uuid + '.osm.pbf'): # Pour tous les fichiers osm.pbf de tmp/region voulue
        print("building_indoor file: " + building_indoor_pbf)
        with subprocess.Popen(
            "osmium export "
            + building_indoor_pbf + " "
            + "--output-format=geojson ",
            shell=True,
            stdout=subprocess.PIPE
        ) as proc_export:#export en geojson
            building_indoor_gdf = geopandas.read_file(proc_export.stdout) #lecture du fichier geojson en geodataframe
        with open("result.json", 'w') as outfile:
            outfile.write(building_indoor_gdf.to_json(na='drop'))

        # xxx = building_indoor_gdf[building_indoor_gdf['geometry'].apply(lambda x : x.type!='Point' and x.type!='LineString')]
        # print(xxx.head())
        # linestrings = building_indoor_gdf[building_indoor_gdf['geometry'].apply(lambda x : x.type=='LineString')]
        # print(linestrings.head())


        buildings = building_indoor_gdf[building_indoor_gdf['building:levels'].notnull()] #Filtrer les donnees non buildings:levels

        # xxx = buildings[buildings['geometry'].apply(lambda x : x.type=='MultiPolygon')]
        # if not xxx.empty:
        #     print(xxx.head())
        buildings = buildings[buildings['geometry'].apply(
            #Ne garder que les MultiLineString, MultiPolygon, et LineString et Polygon qui ont au moins 3 points
            lambda shap : (
                (
                        shap.geom_type=='LineString'
                        or shap.geom_type=='Polygon'
                    ) and len(shap.coords)>2
                ) or (
                    shap.geom_type=='MultiLineString'
                    or shap.geom_type=='MultiPolygon'                    
                )
                # )
        )]
        buildings.loc[:, 'geometry'] = numpy.array([
            Polygon(mapping(shap)['coordinates']) #Transformer les LineString en Polygon
                if shap.geom_type=='LineString' else
                    MultiPolygon(Polygon(coord[0]) for coord in mapping(shap)['coordinates'])
                        if (
                            shap.geom_type=='MultiLineString'
                            or shap.geom_type=='MultiPolygon'
                        ) else shap
                for shap in buildings.geometry
        ],dtype=object)

        # buildings = buildings[buildings['geometry'].apply(lambda x : x.type=='LineString')]

        # buildings = building_indoor_gdf[building_indoor_gdf['building:levels']]
        if 'indoor' not in building_indoor_gdf: #Le mettre plus tot ?
            """Arreter le traitement du fichier osm.pbf.courant"""
            continue
        indoors = building_indoor_gdf[building_indoor_gdf['indoor'].notnull()] #Ne garder que les donnees ayant des donnees indoor
        # print(buildings.head())
        places_gdf = buildings[buildings.geometry.apply(lambda x: indoors.intersects(x).any())] #Tout garder ?
        # places_gdf = building_indoor_gdf
        
        places_geojson = json.loads(places_gdf.to_json(na='drop')) #Charger en json
        for place_feature in places_geojson['features']:
            """Integrer dans building_indoors"""   # UTILE ?
            building_indoors['features'][0]['geometry']['coordinates'].append(
                place_feature['geometry']['coordinates']
            )        

        debug_gdf = building_indoor_gdf[building_indoor_gdf['building:levels'].notnull()] #Pareil que la variable "building"
        debug['features'].extend(json.loads(debug_gdf.to_json(na='drop'))['features'])

        # if (len(places_geojson['features']) > 0):
        #     for feature in places_geojson['features']:
        #         print("properties: " + json.dumps(feature["properties"], sort_keys=True, indent=4))
                # place_geojson = {"type": "FeatureCollection", "features": []}
                # place_geojson['features'] = [feature]

    # print(json.dumps(extracts, sort_keys=True, indent=4))


    #FIN DE LA BOUCLE FOR
    with open('debug.geojson', 'w') as outfile:
        json.dump(debug, outfile) #encodage


    polygon_file = 'buildings_indoor' + my_uuid + '.geojson'
    # print("write: " + output_file)
    with open(polygon_file, 'w') as outfile:
        json.dump(building_indoors, outfile)

    # get all data
    # polygon_file = '/tmp/building_indoors' + my_uuid + ".geojson"
    # with open(polygon_file, 'w') as outfile:
    #     json.dump(building_indoors, outfile)
    places_file_pbf = '/tmp/places' + my_uuid + ".osm.pbf"
    cmd = "osmium extract " \
        + "--strategy=smart " \
        + "--overwrite " \
        + "--progress " \
        + "--polygon=" + polygon_file + " " \
        + "--output=" + places_file_pbf + " " \
        + input_pbf
    print("cmd: " + cmd)
    indoor_filter = subprocess.run(
        cmd,
        shell=True
    )
    places_file_geojson = './places' + my_uuid + ".geojson"
    cmd = "osmium export " \
        + "--overwrite " \
        + "--progress " \
        + "--output=" + places_file_geojson + " " \
        + places_file_pbf
    print("cmd: " + cmd)
    indoor_filter = subprocess.run(
        cmd,
        shell=True
    )



    #                 
    #             
    # indoor_pbf = "/tmp/indoor_" + str(my_uuid) + ".osm.pbf"
    # print("filtering indoors...")


    # building_pbf = "/tmp/building_" + str(my_uuid) + ".osm.pbf"
    # print("filtering buildings...")
    # building_filter = subprocess.Popen(
    #     "osmium tags-filter "
    #     + "--overwrite "
    #     + "--progress "
    #     + "--output-format=pbf "
    #     + "--output=" + building_pbf + " "
    #     + input_pbf + " "
    #     + "w/building:levels",
    #     shell=True
    # )
    # building_filter.communicate()

    # print("extracting indoors to geojson...")
    # with subprocess.Popen(
    #     "osmium export "
    #     + indoor_pbf + " "
    #     + "--output-format=geojson ",
    #     shell=True,
    #     stdout=subprocess.PIPE
    # ) as proc_export:
    #     indoors = geopandas.read_file(proc_export.stdout)

    # print("extracting buildings to geojson...")
    # with subprocess.Popen(
    #     "osmium export "
    #     + building_pbf + " "
    #     + "--output-format=geojson ",
    #     shell=True,
    #     stdout=subprocess.PIPE
    # ) as proc_export:
    #     buildings = geopandas.read_file(proc_export.stdout)

    # print("Polygonizes building geometries...")
    # buildings.loc[:, 'geometry'] = [
    #     Polygon(mapping(x)['coordinates']) for x in buildings.geometry]
    # print("Filtering indoor buildings")
    # places = buildings[buildings.geometry.apply(
    #     lambda x: indoors.intersects(x).any())]
    # print("Writing results...")
    # xxx = json.loads(places.to_json(na='drop'))
    # with open('buildings_indoor.geojson', 'w') as outfile:
    #     json.dump(xxx, outfile)


def main():
    my_uuid = "_" + str(uuid.uuid4())
    # area = "ile-de-france"
    area = "bretagne-latest"
    area = "bretagne_20210308_091733"
    # splitter("bretagne-latest.osm.pbf")
    # $ osmupdate data/bretagne-latest.osm.pbf data/bretagne-latest_last.osm.pbf -B=./data/bretagne.poly
    input_pbf = "data/" + area + ".osm.pbf"
    building_indoor_pbf = "/tmp/" + area + "_building_indoor.osm.pbf"    
    # if not os.path.exists(building_indoor_pbf):
    print("filtering buildings...")
    cmd = "osmium tags-filter " \
        "--progress " \
        "--overwrite " \
        "--output-format=pbf " \
        "--output=" + building_indoor_pbf + " " \
        "" + input_pbf + " " \
        "w/indoor w/building:levels"
    print("cmd: " + cmd)
    building_indoor_filter = subprocess.run(
        cmd,
        shell=True
    )
        # building_indoor_filter.communicate()    
    # indoor_pbf = "/tmp/bretagne_indoor.osm.pbf"
    # if not os.path.exists(indoor_pbf):
    #     print("filtering indoor...")
    #     cmd = "osmium tags-filter " \
    #         "--progress " \
    #         "--output-format=pbf " \
    #         "--output=" + indoor_pbf + " " \
    #         "" + input_pbf + " " \
    #         "w/indoor"
    #     print("cmd: " + cmd)
    #     indoor_filter = subprocess.Popen(
    #         cmd,
    #         shell=True
    #     )
    #     indoor_filter.communicate()    
    # bbox={
    #     "xmin": 62, "ymin": 44,
    #     "xmax": 63, "ymax": 45,
    # }
    bbox={
        "xmin": 0, "ymin": 0,
        "xmax": 1, "ymax": 1,
    }
    
    # splitter(my_uuid=my_uuid, input_pbf=indoor_pbf, zoom=7, max_zoom=18, name="bretagne_indoor", bbox=bbox)
    splitter(my_uuid=my_uuid, input_pbf=building_indoor_pbf, zoom=1, max_zoom=18, name=area + "_building_indoor", bbox=bbox)

    finder(my_uuid=my_uuid, input_pbf=input_pbf, building_indoor_name=area + "_building_indoor")

if __name__ == "__main__":
    main()

