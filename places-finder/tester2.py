#!/usr/bin/python3

import requests
import sys
import json
import math
import uuid
import subprocess
import numpy

from shapely.geometry.base import geometry_type_name
import sqlalchemy
import geopandas
from shapely.geometry import Polygon, Point, mapping
import fiona
import random
import os.path
import os
import glob
from shapely.geometry.multipolygon import MultiPolygon
from datetime import datetime
# from sqlalchemy import create_engine, BigInteger, dialects
from sqlalchemy import Table, MetaData, Column, Integer, String, TIMESTAMP, create_engine, BigInteger, dialects, inspect
from sqlalchemy.dialects.postgresql import insert

# from geopandas.array import GeometryArray, GeometryDtype, from_shapely, to_wkb, to_wkt
import pandas
import typing
from geoalchemy2 import WKTElement, Geometry
# from io import StringIO

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

    unique_id="openindoor_id"
    conn.execute('''
        ALTER TABLE {1} DROP CONSTRAINT IF EXISTS constraint_{2};
        ALTER TABLE {1} ADD CONSTRAINT constraint_{2} PRIMARY KEY({2});
        ALTER TABLE {1} ALTER COLUMN {2} SET NOT NULL;
        ALTER TABLE {1} ALTER COLUMN wkb_geometry TYPE geometry;
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


    gdf.to_sql(
        name = db_table_name,
        con = engine,
        if_exists = 'append',
        index = False,
        dtype = {'geometry': Geometry(geometry_type='POLYGON', srid=4326)},
        method = upsert
)

gdf = geopandas.read_file("mygeojson2.geojson") #lecture du fichier geojson en geodataframe
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

get_duplicates = lambda shap : shap.equals

index_list = []
for shap in gdf_building_indoor.geometry:
    copies = gdf_building_indoor[gdf_building_indoor.geometry.apply(get_duplicates(shap))].geometry
    if copies.index[0] not in index_list:
        index_list.append(copies.index[0])

gdf_building_indoor = gdf_building_indoor.loc[index_list]

print(gdf_building_indoor)
print(gdf_building_indoor.geometry.apply(lambda geom: WKTElement(geom.wkt, srid=4326)))

# gdf_to_db(gdf=gdf_building_indoor,
#         system="postgresql",
#         user="openindoor-db-admin",
#         password=os.environ["POSTGRES_PASSWORD"],
#         server="openindoor-db",
#         port=5432,
#         db_name="openindoor-db",
#         db_table_name="building_footprint")