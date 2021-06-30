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
import pandas
import random
import os.path
import os
import glob
from shapely.geometry.multipolygon import MultiPolygon
from shapely.ops import unary_union
import numpy
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
        input_pbf="data/europe_france_bretagne/indoor/building_indoor.osm.pbf",
        zoom=1,
        max_zoom = 18,
        bbox={"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1},
        region_name="europe_france_bretagne"
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
    indoor_path = "data/" + region_name + "/indoor/"
    for x in [bbox["xmin"], bbox["xmax"]]:
        for y in [bbox["ymin"], bbox["ymax"]]:
            (lon0, lat0) = num2deg(x, y, zoom)
            (lon1, lat1) = num2deg(x+1, y+1, zoom)
            filename = indoor_path + "split/" + \
                str(zoom) + "_" \
                + str(x) + "_" + str(y) + "_" + str(x + 1) + "_" + str(y + 1) \
                + ".osm.pbf"
            print("setting file: " + filename)
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
    conf = indoor_path + region_name + '_config.json'
    print("conf:" + conf)
    # print(json.dumps(extracts, sort_keys=True, indent=4))
    with open(conf, 'w') as outfile:
        json.dump({"extracts": extracts}, outfile)
        outfile.flush()
    cmd = "osmium extract " \
        + "--strategy=smart " \
        + "--overwrite " \
        + "--progress " \
        + "--config=" + conf + " " \
        + input_pbf
    # os.remove(input_pbf)

    print("cmd: " + cmd)
    indoor_filter = subprocess.run(cmd,shell=True)
    # indoor_filter.communicate()


    for my_finder in my_finders:
        size = os.path.getsize(my_finder["input_pbf"])
        if size > 100000 and zoom < max_zoom:
            splitter(
                input_pbf=my_finder["input_pbf"],
                zoom=my_finder["zoom"],
                max_zoom=max_zoom,
                region_name=region_name,
                bbox=my_finder["bbox"]
            )
            os.remove(my_finder["input_pbf"])
        elif size < 100:
            os.remove(my_finder["input_pbf"])
            #print("removed because size too small")
        else:
            print("Working with file : ",my_finder["input_pbf"])
            finder(file_name=my_finder["input_pbf"],region_name=region_name)
            #os.remove(my_finder["input_pbf"])

def pbf_extractor(region):
    """
    Generation des fichiers pbf

    Entree :

    region : tableau correspondant a la region
    """
    region_name=region["name"]
    region_poly=region["poly"]
    region_pbf=region["pbf"]
    os.makedirs("data/"+ region_name + "/indoor/split", exist_ok=True) #Creation des répertoires
    os.makedirs("data/"+ region_name + "/geofabrik_files", exist_ok=True)

    indoor_path = "data/" + region_name + "/indoor/"
    geofabrik_path = "data/" + region_name + "/geofabrik_files/"

    poly_file = geofabrik_path + region_name + ".poly"
    old_pbf_file = geofabrik_path + region_name + ".osm.pbf"
    if not os.path.isfile(poly_file):
        """Telechargement du fichier poly s'il n'est pas dans le path"""
        print("download: " + poly_file)
        wget.download(region_poly, poly_file)
    if not os.path.isfile(old_pbf_file):
        """Telechargement du fichier pbf s'il n'est pas dans le path"""
        print("download: " + region_pbf)
        wget.download(region_pbf, old_pbf_file)

    now = datetime.now()
    dt_string = now.strftime("%Y%m%d_%H%M%S") #String de la date et heure
    new_pbf_file = indoor_path + region_name + "_" + dt_string + ".osm.pbf"

    # cmd = [
    #     "osmupdate",
    #      old_pbf_file,
    #      new_pbf_file,
    #      "-B=" + poly_file
    #  ] #Mise a jour du fichier pbf. -B= pour ne garder que la region voulue
    # print(cmd)
    # building_indoor_filter = subprocess.run(cmd)


    #____________MODE DEBUG_______________
    new_pbf_file=old_pbf_file

    building_indoor_pbf = indoor_path + "building_indoor.osm.pbf" #Chemin du fichier pbf
    cmd = \
        "osmium "+ \
        "tags-filter "+\
        "--progress "+\
        "--overwrite "+\
        "--output-format=pbf " +\
        "--output=" + building_indoor_pbf + " " +\
        new_pbf_file + " " +\
        "w/indoor w/building:levels"
    #Filtrage du fichier pbf pour ne garder que les batiments voulus.
    print(cmd)
    building_indoor_filter = subprocess.run(cmd, shell=True)

    #Decoupage du fichier en 4
    splitter(
        input_pbf=building_indoor_pbf,
        zoom=1,
        max_zoom=18,
        region_name=region_name,
        bbox={
            "xmin": 0, "ymin": 0,
            "xmax": 1, "ymax": 1,
        }
    )
    # finder(
    #     input_pbf=building_indoor_pbf,
    #     region_name=region_name
    # )

def finder(
    file_name,
    region_name
):
    """
    Entrees :
    file_name : fichier à traiter
    """
    print("Appel finder")
    indoor_path = "data/" + region_name + "/indoor/"
    # building_indoor = {"type": "FeatureCollection", "features": [
    #     {"type":"Feature","geometry":{
    #         "type":"MultiPolygon",
    #         "coordinates":[]
    #     }}
    #    ]
    # }
    with subprocess.Popen(
        "osmium export "
        + file_name + " "
        + "--output-format=geojson "
        + "--add-unique-id=type_id ",
        shell=True,
        stdout=subprocess.PIPE
    ) as proc_export:#export en geojson
        gdf = geopandas.read_file(proc_export.stdout) #lecture du fichier geojson en geodataframe

    if 'indoor' not in gdf:
        #print("No indoor data detected")
        return None

    gdf.rename(columns={"id":"openindoor_id"},inplace=True)
    
    tab = numpy.empty([gdf.shape[0],1],dtype=object)
    tab[:,0] = [
        Polygon(mapping(shap)['coordinates']) #Corriger les mauvais LineString
            if shap.geom_type=='LineString' and shap.coords[0] == shap.coords[-1] else
                Polygon(mapping(shap)['coordinates'][0][0]) if shap.geom_type=='MultiPolygon' and len(shap)==1 else #Transformer les MultiPolygons n'ayant qu'un seul Polygon en Polygon
                    MultiPolygon(Polygon(coord[0]) for coord in mapping(shap)['coordinates'])
                        if (
                            shap.geom_type=='MultiLineString'
                            or shap.geom_type=='MultiPolygon'
                        ) else shap
            for shap in gdf.geometry
    ]
    gdf.loc[:, 'geometry'] = tab
    #print("Correction LineStrings to Polygons done")

    gdf_indoor = gdf[gdf['indoor'].notnull()] #Ne garder que les donnees ayant des donnees indoor
    gdf_indoor = gdf_indoor[gdf_indoor['indoor']!='no']
    gdf_indoor = gdf_indoor.drop_duplicates(subset=["geometry"])

    if gdf_indoor.empty:
        print("No indoor data detected")
        return None
    print("Indoor data filtered")

    gdf_building = gdf[gdf["building"].notnull()]
    gdf_building = gdf_building[gdf_building["building"]!='no']

    #Contient les Polygon/MultiPolygon en intersection avec une donnée indoor
    #gdf_building_indoor = gdf[gdf["geometry"].apply(lambda shap : shap if (shap.geom_type in ['Polygon','MultiPolygon'] and gdf_indoor.intersects(shap).any()) else None).notnull()].geometry
    # border = gdf_building_indoor.unary_union
    # if border.geom_type=='Polygon':
    #     row = {"geometry":Polygon(border.exterior)}
    #     gdf_building_indoor = geopandas.GeoDataFrame(columns=["geometry"])
    #     gdf_building_indoor = gdf_building_indoor.append(row,ignore_index=True)
    # else:
    #     gdf_building_indoor = geopandas.GeoDataFrame([Polygon(shap.exterior) for shap in gdf_building_indoor.unary_union],columns=["geometry"])
    #gdf_building_indoor = geopandas.GeoDataFrame(gdf_building_indoor,columns=["geometry"])
    
    get_polygon_indoor_building = lambda shap : gdf_indoor.intersects(shap).any()

    gdf_building_indoor = gdf_building[gdf_building["geometry"].apply(get_polygon_indoor_building)].drop_duplicates()




    get_polygon_indoor_building_footprint = lambda shap : not(gdf_building_indoor[gdf_building_indoor.geometry.apply(lambda shap2 : not(shap2.equals(shap)))].contains(shap).any())
    gdf_building_indoor = gdf_building_indoor[gdf_building_indoor.geometry.apply(get_polygon_indoor_building_footprint)]
    gdf_building_indoor.dropna(axis=1,how="all",inplace=True)

    if gdf_building_indoor.empty :
        return None

    get_duplicates = lambda shap : shap.equals

    index_list = []
    for shap in gdf_building_indoor.geometry:
        copies = gdf_building_indoor[gdf_building_indoor.geometry.apply(get_duplicates(shap))].geometry
        if copies.index[0] not in index_list:
            index_list.append(copies.index[0])

    gdf_building_indoor = gdf_building_indoor.loc[index_list]
    
    sqlcommand="ALTER TABLE building_footprint "

    n = len(gdf_building_indoor.columns)
    for i in range(n-1):
        sqlcommand+="ADD COLUMN IF NOT EXISTS \"{}\" VARCHAR(255)".format(gdf_building_indoor.columns[i])
        if i<n-2:
            sqlcommand+=","
        else:
            sqlcommand+=";"

    cmd="psql -h openindoor-db -d openindoor-db -p 5432 -U openindoor-db-admin --command='{}'".format(sqlcommand)
    print(cmd)
    if n>1:
        sqlrun = subprocess.run(cmd, shell=True)
    
    #print("gdf with building with indoor created")

        #Regrouper les polygones qui se superposent en un seul polygone
        # new_polys=[]
        # gdf_copy = gdf_building_indoor
        # for shap in gdf_building_indoor:
        #     if shap in gdf_copy:
        #         l = get_all_intersections(gdf_copy, shap)
        #         if len(l)>1:
        #             gdf_copy = gdf_copy[gdf_copy.apply(lambda shap : shap not in l)]
        #             new_polys.append(unary_union(l))
        #
        # gdf_building_indoor = gdf_building_indoor.append(geopandas.GeoSeries(new_polys))
        # gdf_building_indoor = gdf_building_indoor.drop_duplicates()
        #gdf_building_indoor = geopandas.GeoDataFrame(gdf_building_indoor,columns=["geometry"])

        # for i in range(gdf_building_indoor.shape[0]):
        #     single_building = {"type": "FeatureCollection", "features": [
        #         {"type":"Feature","geometry":{
        #             "type":"Polygon",
        #             "coordinates":[]
        #         }}
        #         ]
        #     }
        #     single_building['features'][0]['geometry']['coordinates'].append(list(gdf_building_indoor.geometry.iloc[i].exterior.coords))
        #     single_building_poly = "data/" + region_name + "/indoor/single_building_poly.geojson"
        #     with open(single_building_poly) as outfile:
        #         json.dump(single_building,outfile)
        #     single_building_pbf = "data/" + region_name + "/indoor/single_building.osm.pbf"
        #     cmd = "osmium extract " \
        #         + "--strategy=simple " \
        #         + "--overwrite " \
        #         + "--progress " \
        #         + "--polygon=" + single_building_poly + " " \
        #         + "--output=" + single_building_pbf + " " \
        #         + input_pbf
        #     indoor_filter = subprocess.run(
        #         cmd,
        #         shell=True
        #     )
        #     with subprocess.Popen(
        #         "osmium export"
        #         + "--overwrite"
        #         + "--progress"
        #         + single_building_pbf + " "
        #         + "--output-format=geojson ",
        #         shell=True,
        #         stdout=subprocess.PIPE
        #     ) as proc_export:#export en geojson
        #         gdf_single_building = geopandas.read_file(proc_export.stdout) #lecture du fichier geojson en geodataframe
        #     gdf_single_building["openindoor:parent_building_id"] = gdf_building_indoor["openindoor:building_id"].iloc[i]
        #     gdf_single_building["openindoor:id"]=[j + id_element for j in range(gdf_single_building.shape[0])]
        #     id_element+=gdf_single_building.shape[0]

    places_geojson = json.loads(gdf_building_indoor.to_json(na='drop')) #Charger en json
    # for place_feature in places_geojson['features']:
    #     """Integrer dans building_indoors"""
    #     coordinates = place_feature['geometry']['coordinates']
    #     building_indoor['features'][0]['geometry']['coordinates'].append(coordinates)
    # print("coordinates registered")

    polygon_file = indoor_path + "building_indoor_polygon.geojson"


    # print("write: " + output_file)
    with open(polygon_file, 'w') as outfile:
        json.dump(places_geojson, outfile)
        outfile.flush()

    cmd = "ogr2ogr " \
        + "-update " \
        + "-append " \
        + "-f " \
        + "\"PostgreSQL\" PG:\"dbname='openindoor-db' host='openindoor-db' port='5432' user='openindoor-db-admin' password='{}'\" ".format(os.environ['POSTGRES_PASSWORD']) \
        + polygon_file + " " \
        + "-nln public.building_footprint " \
        + "-skipfailures"
    print("cmd: " + cmd)
    ddb_insert = subprocess.run(
        cmd,
        shell=True
    )




    # places_file_pbf = 'data/' + region_name + "/indoor/building_with_indoor.osm.pbf"
    # cmd = "osmium extract " \
    #     + "--strategy=simple " \
    #     + "--overwrite " \
    #     + "--progress " \
    #     + "--polygon=" + polygon_file + " " \
    #     + "--output=" + places_file_pbf + " " \
    #     + input_pbf
    # print("cmd: " + cmd)
    # indoor_filter = subprocess.run(
    #     cmd,
    #     shell=True
    # )
    # places_file_geojson = 'data/' +  region_name + "/indoor/building_with_indoor.geojson"
    # cmd = "osmium export " \
    #     + "--overwrite " \
    #     + "--progress " \
    #     + "--output=" + places_file_geojson + " " \
    #     + places_file_pbf
    # print("cmd: " + cmd)
    # indoor_filter = subprocess.run(
    #     cmd,
    #     shell=True
    # )
    # print("Cleaning bad data")
    # gdf_cleaning = geopandas.read_file(places_file_geojson)
    # n = gdf_cleaning.shape[0]
    # tab = numpy.empty([gdf_cleaning.shape[0],1],dtype=object)
    # tab[:,0] = [
    #     Polygon(mapping(shap)['coordinates']) #Corriger les mauvais LineString
    #         if shap.geom_type=='LineString' and shap.coords[0] == shap.coords[-1] else
    #             Polygon(mapping(shap)['coordinates'][0][0]) if shap.geom_type=='MultiPolygon' and len(shap)==1 else
    #                 MultiPolygon(Polygon(coord[0]) for coord in mapping(shap)['coordinates'])
    #                     if (
    #                         shap.geom_type=='MultiLineString'
    #                         or shap.geom_type=='MultiPolygon'
    #                     ) else shap
    #         for shap in gdf_cleaning.geometry
    # ]
    # gdf_cleaning.loc[:, 'geometry'] = tab
    #
    # gdf_indoor_cleaning = gdf_cleaning[gdf_cleaning['indoor'].notnull()]
    # gdf_indoor_cleaning = gdf_indoor_cleaning[gdf_indoor_cleaning['indoor']!='no']
    # gdf_indoor_cleaning.drop_duplicates(subset=["geometry"], inplace=True)
    #
    #
    # gdf_building_indoor_cleaning = gdf_cleaning[gdf_cleaning["geometry"].apply(lambda shap : shap if (shap.geom_type in ['Polygon','MultiPolygon'] and gdf_indoor_cleaning.intersects(shap).any()) else None).notnull()].geometry
    # border_cleaning = gdf_building_indoor_cleaning.unary_union
    # if border_cleaning.geom_type=='Polygon':
    #     row = {"geometry":Polygon(border_cleaning.exterior)}
    #     gdf_building_indoor_cleaning = geopandas.GeoDataFrame(columns=["geometry"])
    #     gdf_building_indoor_cleaning = gdf_building_indoor_cleaning.append(row,ignore_index=True)
    # else:
    #     gdf_building_indoor_cleaning = geopandas.GeoDataFrame([Polygon(shap.exterior) for shap in gdf_building_indoor_cleaning.unary_union],columns=["geometry"])
    #
    # gdf_clean = gdf_cleaning[gdf_cleaning["geometry"].apply(lambda shap : gdf_building_indoor_cleaning.intersects(shap).any())]
    #
    # places_file_geojson_cleaning = 'data/' +  region_name + "/indoor/building_with_indoor_clean.geojson"
    # print("data cleaned : ",n-gdf_clean.shape[0])
    #
    #
    # with open(places_file_geojson_cleaning,"w") as outfile:
    #     json.dump(json.loads(gdf_clean.to_json(na="drop")), outfile)

def main():
    #print("coucou")
    with open('regions.json') as regions:
        region_data = json.load(regions)
    for region in region_data['regions']:
        pbf_extractor(region)

if __name__ == "__main__":
    main()

