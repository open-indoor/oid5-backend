#!/usr/bin/python3

import requests
import sys
import json
import math
import uuid
import subprocess
import geopandas
from shapely.geometry import Polygon, Point, mapping
from shapely.geometry.base import geometry_type_name
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
from sqlalchemy import Table, MetaData, Column, Integer, String, TIMESTAMP, create_engine, BigInteger, dialects, inspect
from sqlalchemy.dialects.postgresql import insert
from geoalchemy2 import WKTElement, Geometry

with open('regions.json') as regions:
    region_data = json.load(regions)
region = region_data["regions"][0]
region_name=region["name"]
region_poly=region["poly"]
region_pbf=region["pbf"]

geofabrik_path = "data/" + region_name + "/geofabrik_files/"

poly_file = geofabrik_path + region_name + ".poly"
old_pbf_file = geofabrik_path + region_name + ".osm.pbf"

os.makedirs("data/"+ region_name + "/geofabrik_files", exist_ok=True)


if not os.path.isfile(poly_file):
    """Telechargement du fichier poly s'il n'est pas dans le path"""
    print("download: " + poly_file)
    wget.download(region_poly, poly_file)
if not os.path.isfile(old_pbf_file):
    """Telechargement du fichier pbf s'il n'est pas dans le path"""
    print("download: " + region_pbf)
    wget.download(region_pbf, old_pbf_file)
def upsert(table, conn, keys, data_iter):
    """
    Execute SQL statement inserting data

    Parameters
    ----------
    table : pandas.io.sql.SQLTable
    conn : sqlalchemy.engine.Engine or sqlalchemy.engine.Connection
    keys : list of str
        Column names
    data_iter : Iterable that iterates the values to be inserted
    unique_id : primary key
    """
    # print("table:" + table.table.name)

    # Add contraint if missing

    unique_id="openindoor_id_item"
    conn.execute('''
        ALTER TABLE {1} DROP CONSTRAINT IF EXISTS constraint_{2};
        ALTER TABLE {1} ADD CONSTRAINT constraint_{2} PRIMARY KEY({2});
        ALTER TABLE {1} ALTER COLUMN {2} SET NOT NULL;
        ALTER TABLE {1} ALTER COLUMN geometry TYPE geometry;
        ALTER TABLE {1} ALTER COLUMN openindoor_item_centroid TYPE geometry;
        ALTER TABLE {1} DROP CONSTRAINT IF EXISTS FK_building_id;
        ALTER TABLE {1} ADD CONSTRAINT FK_building_id FOREIGN KEY (openindoor_building_id) REFERENCES building_footprint(openindoor_id) ON DELETE CASCADE ON UPDATE CASCADE
    '''.replace('{1}', table.table.name).replace('{2}', unique_id))

    insert_stmt=insert(table.table)
    # Prepare upsert statement
    my_dict={}
    for key in keys:
        my_dict[key]=insert_stmt.excluded[key]
        # Create column if missing
        conn.execute('''
            ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} {};
        '''.format(
            table.table.name,
            '"' + key + '"',
            insert_stmt.excluded[key].type)
        )
    upsert_stmt=insert_stmt.on_conflict_do_update(
        index_elements = [unique_id],
        set_ = my_dict
    )
    data=[dict(zip(keys, row)) for row in data_iter]
    conn.execute(upsert_stmt, data)

def gdf_to_db(gdf, system, user, password, server, port, db_name, db_table_name):
    engine=create_engine(system + "://" + user + ":" + password +"@" + server + ":" + str(port) + "/" + db_name)


    gdf['geometry']=gdf.geometry.apply(lambda geom: WKTElement(geom.wkt, srid=4326))
    gdf['openindoor_item_centroid']=gdf['openindoor_item_centroid'].apply(lambda geom: WKTElement(geom.wkt, srid=4326))


    gdf.to_sql(
        name = db_table_name,
        con = engine,
        if_exists = 'append',
        index = False,
        dtype = {'geometry': Geometry(geometry_type='GEOMETRY', srid=4326),\
                'openindoor_item_centroid': Geometry(geometry_type='POINT', srid=4326)},
        method = upsert
)

db_connection_url = "postgresql://openindoor-db-admin:admin123@openindoor-db:5432/openindoor-db"
con = create_engine(db_connection_url)  
sql = "SELECT openindoor_id, geometry FROM building_footprint"
gdf = geopandas.GeoDataFrame.from_postgis(sql, con, geom_col="geometry")  


building_indoor = {"type": "FeatureCollection", "features": [
    {"type":"Feature","geometry":{
        "type":"MultiPolygon",
        "coordinates":[]
    }}
    ]
}

with open("building_footprint.geojson", 'w') as outfile:
    json.dump(json.loads(gdf.to_json()), outfile)
    outfile.flush()

places_geojson = json.loads(gdf.to_json()) #Charger en json
for place_feature in places_geojson['features']:
    """Integrer dans building_indoors"""
    if place_feature['geometry']['type']=="Polygon":
        coordinates = place_feature['geometry']['coordinates']
        building_indoor['features'][0]['geometry']['coordinates'].append(coordinates)
    elif place_feature['geometry']['type']=="MultiPolygon":
        for polygon in place_feature['geometry']['coordinates']:
            building_indoor['features'][0]['geometry']['coordinates'].append(polygon)
polygon_file = 'buiding_footprint_poly.geojson'

with open(polygon_file, 'w') as outfile:
    json.dump(building_indoor, outfile)
    outfile.flush()

input_pbf = "data/europe_france_bretagne/geofabrik_files/europe_france_bretagne.osm.pbf"
output_pbf = "building_with_data.osm.pbf"

cmd = "osmium extract " \
        + "--strategy=simple " \
        + "--overwrite " \
        + "--progress " \
        + "--polygon=" + polygon_file + " " \
        + "--output=" + output_pbf + " " \
        + input_pbf
print(cmd)
subprocess.run(cmd,shell=True)

with subprocess.Popen(
        "osmium export "
        + output_pbf + " "
        + "--output-format=geojson "
        + "--add-unique-id=type_id ",
        shell=True,
        stdout=subprocess.PIPE
    ) as proc_export:#export en geojson
        gdf2 = geopandas.read_file(proc_export.stdout) #lecture du fichier geojson en geodataframe

gdf2.rename(columns={"id":"openindoor_id_item"},inplace=True)
tab = numpy.empty([gdf2.shape[0],1],dtype=object)
tab[:,0] = [
    Polygon(mapping(shap)['coordinates']) #Corriger les mauvais LineString
        if shap.geom_type=='LineString' and shap.coords[0] == shap.coords[-1] else
            Polygon(mapping(shap)['coordinates'][0][0]) if shap.geom_type=='MultiPolygon' and len(shap)==1 else #Transformer les MultiPolygons n'ayant qu'un seul Polygon en Polygon
                MultiPolygon(Polygon(coord[0]) for coord in mapping(shap)['coordinates'])
                    if (
                        shap.geom_type=='MultiLineString'
                        or shap.geom_type=='MultiPolygon'
                    ) else shap
        for shap in gdf2.geometry
]
gdf2.loc[:, 'geometry'] = tab

get_duplicates = lambda shap : shap.equals

gdf_final = geopandas.GeoDataFrame()
for i in range(gdf.shape[0]):
    id = gdf.iloc[i]["openindoor_id"]
    polygon = gdf.iloc[i].geometry

    gdf_building = gdf2[gdf2.geometry.apply(lambda shap : polygon.contains(shap) or polygon.boundary.contains(shap))]
    gdf_building = gdf_building[gdf_building.geometry.apply(lambda shap : not(shap.equals(polygon)))]
    if not(gdf_building.empty):
        gdf_building.dropna(axis=1,how='all',inplace=True)
        gdf_building["openindoor_building_id"] = id

        tab = numpy.empty([gdf_building.shape[0],1],dtype=object)
        tab[:,0] = [
            Polygon(mapping(shap)['coordinates']) #Corriger les mauvais LineString
                if shap.geom_type=='LineString' and shap.coords[0] == shap.coords[-1] else
                    Polygon(mapping(shap)['coordinates'][0][0]) if shap.geom_type=='MultiPolygon' and len(shap)==1 else
                        MultiPolygon(Polygon(coord[0]) for coord in mapping(shap)['coordinates'])
                            if (
                                shap.geom_type=='MultiLineString'
                                or shap.geom_type=='MultiPolygon'
                            ) else shap
                for shap in gdf_building.geometry
        ]
        gdf_building.loc[:, 'geometry'] = tab

        index_list = []
        for shap in gdf_building.geometry:
            copies = gdf_building[gdf_building.geometry.apply(get_duplicates(shap))].geometry
            if copies.index[0] not in index_list:
                index_list.append(copies.index[0])
                
        gdf_building = gdf_building.loc[index_list,:]
        
        gdf_final = gdf_final.append(gdf_building)


gdf_final.drop_duplicates(subset=["openindoor_id_item"],inplace=True) #donnees presentes dans 2 batiments

gdf_final["openindoor_item_centroid"]=gdf_final.centroid
gdf_final["openindoor_geomtype"]=gdf_final.geom_type

mygdf=gdf_final

with open("keep.json") as keep:
    keep_data = json.load(keep)
serie = mygdf.isnull().sum().apply(lambda n : n/mygdf.shape[0]*100<95)
keep_list = serie.loc[serie].index
keep_list = keep_list.union(keep_data["footprint_key"])
mygdf.drop(axis=1,columns=(mygdf.columns.difference(keep_list)),inplace=True)

gdf_to_db(gdf=mygdf,
    system="postgresql",
    user="openindoor-db-admin",
    password=os.environ["POSTGRES_PASSWORD"],
    server="openindoor-db",
    port=5432,
    db_name="openindoor-db",
    db_table_name="building_item")