#!/usr/bin/python3

import requests
import sys
import json
import math
import uuid
import subprocess

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

print(geopandas.__version__)
print(pandas.__version__)
print(sqlalchemy.__version__)

unique_id = 'openindoor_id'


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
    """
    # print("table:" + table.table.name)

    # Add contraint if missing
    conn.execute('''
        ALTER TABLE {1} DROP CONSTRAINT IF EXISTS constraint_{2};
        ALTER TABLE {1} ADD CONSTRAINT constraint_{2} PRIMARY KEY({2});
        ALTER TABLE {1} ALTER COLUMN {2} SET NOT NULL;
        ALTER TABLE {1} ALTER COLUMN geometry TYPE geometry;
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
            key,
            insert_stmt.excluded[key].type)
        )
    upsert_stmt=insert_stmt.on_conflict_do_update(
        index_elements = [unique_id],
        set_ = my_dict
    )
    data=[dict(zip(keys, row)) for row in data_iter]
    conn.execute(upsert_stmt, data)


crs={'init': 'epsg:4326'}

mygdf=geopandas.read_file("mygeojson.geojson", crs = crs)

# mygdf = mygdf.set_crs("EPSG:4326")
# mygdf = mygdf.to_crs("EPSG:4326")

engine=create_engine(
    "postgresql://openindoor-db-admin:admin123@openindoor-db:5432/openindoor-db")

mygdf.rename(columns={"id":unique_id},inplace=True)

mygdf['geometry']=mygdf.geometry.apply(
    lambda geom: WKTElement(geom.wkt, srid=4326))

print(mygdf)

mygdf.to_sql(
    name = "my_table",
    con = engine,
    if_exists = 'append',
    index = False,
    dtype = {'geometry': Geometry(geometry_type='POINT', srid=4326)},
    method = upsert


)
