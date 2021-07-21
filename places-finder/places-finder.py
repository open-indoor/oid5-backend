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
from shapely.geos import TopologicalError
import numpy
import wget
from datetime import datetime
from sqlalchemy import Column, Integer, String, TIMESTAMP, create_engine, BigInteger, dialects, inspect
from sqlalchemy.dialects.postgresql import insert
from geoalchemy2 import WKTElement, Geometry
import hashlib
import traceback
# from pyrosm import OSM
# from pyrosm import get_data

unique_id = 'id'
pbf_max_size = 1000
pbf_min_size = 92
# unique_id = 'openindoor_id'

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

engine=create_engine(
    "postgresql://openindoor-db-admin:admin123@openindoor-db:5432/openindoor-db")

def default_importer(my_file):
    print('Nothing to do with:' + my_file)

def splitter(
        indoor_pbf="/data/tmp/europe_france_bretagne/indoor.osm.pbf",
        building_pbf="/data/tmp/europe_france_bretagne/building.osm.pbf",
        max_zoom = 18,
        min_zoom = 15,
        bbox={"zoom": 1, "xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1},
        region_name="europe_france_bretagne",
        method = default_importer,
    ):

    indoor_extracts = []
    building_extracts = []
    my_finders = []
    tile_name = str(bbox["zoom"]) + "_" + str(bbox["xmin"]) + "_" + str(bbox["ymin"]) + "_" + str(bbox["xmax"]) + "_" + str(bbox["ymax"])
    for x in range(bbox["xmin"], bbox["xmax"] + 1):
        for y in range(bbox["ymin"], bbox["ymax"] + 1):
            (lon0, lat0) = num2deg(x, y, bbox["zoom"])
            (lon1, lat1) = num2deg(x+1, y+1, bbox["zoom"])
            sub_tile_name = str(bbox["zoom"]) + "_" + str(x) + "_" + str(y) + "_" + str(x + 1) + "_" + str(y + 1)
            indoor_filename = "/data/tmp/" + region_name + "/indoor_" + sub_tile_name + ".osm.pbf"
            building_filename = "/data/tmp/" + region_name + "/building_" + sub_tile_name + ".osm.pbf"
            print("Will generate: " + indoor_filename)
            # print("setting file: " + filename)
            indoor_extracts.append({
                "output": indoor_filename,
                "output_format": "pbf",
                "bbox": [lon0, lat0, lon1, lat1]
            })
            building_extracts.append({
                "output": building_filename,
                "output_format": "pbf",
                "bbox": [lon0, lat0, lon1, lat1]
            })
            my_finders.append({
                "indoor_pbf": indoor_filename,
                "building_pbf": building_filename,
                "lonlat_bbox": [lon0, lat0, lon1, lat1],
                "bbox": {
                    "zoom": bbox["zoom"] + 1,
                    "xmin": x * 2, "ymin": y * 2,
                    "xmax": (2*x) + 1, "ymax": (2*y) + 1
                }
            })
    indoor_conf = '/data/tmp/' + region_name + '/indoor_config' + "_"  + tile_name + '.json'
    building_conf = '/data/tmp/' + region_name + '/building_config' + "_"  + tile_name + '.json'
    print("indoor_conf:" + indoor_conf)
    with open(indoor_conf, 'w') as outfile:
        json.dump({"extracts": indoor_extracts}, outfile)
        outfile.flush()
        cmd = [
            "osmium", "extract",
            "--strategy=smart",
            "--overwrite",
            "--progress",
            "--fsync",
            "--config=" + indoor_conf,
            indoor_pbf
        ]
        print("cmd: " + str(cmd))
        subprocess.run(cmd)

    with open(building_conf, 'w') as outfile:
        json.dump({"extracts": building_extracts}, outfile)
        outfile.flush()
        cmd = [
            "osmium", "extract",
            # "--strategy=smart",
            "--strategy=complete_ways",
            "--overwrite",
            "--progress",
            "--fsync",
            "--config=" + building_conf,
            building_pbf
        ]
        print("cmd: " + str(cmd))
        subprocess.run(cmd)

    print(glob.glob("/data/tmp/*.osm.pbf"))
    for my_finder in my_finders:
        print("Analyse: " + my_finder["indoor_pbf"])
        pbf_size = os.path.getsize(my_finder["indoor_pbf"])
        print("pbf_size:", pbf_size)
        if (pbf_size > pbf_max_size and bbox["zoom"] < max_zoom) or (pbf_size > pbf_min_size and bbox["zoom"] < min_zoom):
            splitter(
                indoor_pbf=my_finder["indoor_pbf"],
                building_pbf=my_finder["building_pbf"],
                max_zoom=max_zoom,
                min_zoom = min_zoom,
                region_name=region_name,
                bbox=my_finder["bbox"],
                method = method,
            )
            # os.remove(my_finder["input_pbf"])
        # elif pbf_size <= pbf_min_size:
        #     pass
            # os.remove(my_finder["input_pbf"])
        elif pbf_size > pbf_min_size:
            # print('Going to import: ' + my_finder["input_pbf"])
            # print('pbf size: ' + str(os.path.getsize(my_finder["input_pbf"])))
            # print("call to: " + method.__name__)

            method(my_finder["indoor_pbf"], my_finder["building_pbf"], region_name = region_name)

        os.remove(my_finder["indoor_pbf"])
        os.remove(my_finder["building_pbf"])

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
        ALTER TABLE {1} DROP CONSTRAINT IF EXISTS constraint_{1}_{2};
        ALTER TABLE {1} ADD CONSTRAINT constraint_{1}_{2} UNIQUE ({2});
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
            ALTER TABLE {} ADD COLUMN IF NOT EXISTS "{}" {};
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


# def clean_up():
def fix_shap(shap):
    if ((shap.geom_type=='LineString') and len(shap.coords)>2):
        return Polygon(mapping(shap)['coordinates'])
    elif (shap.geom_type=='MultiLineString' or shap.geom_type=='MultiPolygon'):
        try:

            # print('len(shap.coords):', len(mapping(shap)['coordinates'][0]))
            # print('shap.coords:', mapping(shap)['coordinates'][0])
            # mapping(shap)['coordinates']
            # # [(((1.7089012, 48.9942454), (1.7089605, 48.9942091), (1.7091219, 48.9943235), (1.7091458, 48.9943403), (1.7091174, 48.9943569), (1.709086, 48.9943757), (1.7090578, 48.9943559), (1.7090367, 48.9943689), (1.7089932, 48.9943383), (1.709005, 48.994331), (1.7089842, 48.9943165), (1.7089233, 48.9942737), (1.7089328, 48.9942678), (1.7089012, 48.9942454)),)]
            # mapping(shap)['coordinates'][0]
            # # (((1.7089012, 48.9942454), (1.7089605, 48.9942091), (1.7091219, 48.9943235), (1.7091458, 48.9943403), (1.7091174, 48.9943569), (1.709086, 48.9943757), (1.7090578, 48.9943559), (1.7090367, 48.9943689), (1.7089932, 48.9943383), (1.709005, 48.994331), (1.7089842, 48.9943165), (1.7089233, 48.9942737), (1.7089328, 48.9942678), (1.7089012, 48.9942454)),)
            # for sub_shap in mapping(shap)['coordinates'][0]:
            #     print(sub_shap)
            # # print('shap:', mapping(shap)['coordinates'])
            # for sub_shap in mapping(shap)['coordinates']:
            #     print('sub_shap:', sub_shap)
            #     print('sub_shap len:', len(sub_shap))
            # print(coord for coord in mapping(shap)['coordinates'] if len(coord) > 2)
            multipolygon = MultiPolygon([Polygon(sub_shap) for sub_shap in mapping(shap)['coordinates'][0] if len(sub_shap) > 2])
            return multipolygon
        except Exception as e:
            print('shap.geom_type:', shap.geom_type)
            print('shap:', shap)
            print(e)
            print("Unexpected error:", sys.exc_info()[0])
            traceback.print_exc()
            # traceback.print_stack()
            sys.exit(1)


    else:
        return shap


def inside(shap, indoors):
    if (shap.geom_type=='MultiPolygon'):
        # print('intersects multipolygon')
        # shap_ = shap[~shap.is_valid]
        for polygon in list(shap):
            # my_geo = geopandas.GeoSeries(data=[polygon], crs="EPSG:4326")
            # my_geo.set_crs({'init': 'epsg:4326'})
            # my_geo.to_crs({'init': 'epsg:4326'})
            try:
                # print(indoors.to_crs())
                if (indoors.intersects(polygon).any()):
                    return True
            except Exception as e:
                my_geo = geopandas.GeoSeries(data=[polygon], crs="EPSG:4326")
                print(my_geo.to_json())
                print('valid geo:', my_geo.is_valid)
                print("Unexpected error:", sys.exc_info()[0])
                print(e)
                traceback.print_exc()
                sys.exit(1)
        return False
        # try:
        #     return indoors.intersects(shap).any()
        # except:
        #     print(traceback.format_exc(), file=sys.stderr)         
        #     return False

    else:
        # print('intersects polygon')
        try:
            return indoors.intersects(shap).any()
        except TopologicalError:
            print(traceback.format_exc(), file=sys.stderr)         
            return False


def process_tile(indoor_pbf, building_pbf, region_name = None):
    # pbf_file = pbf_zone["input_pbf"]
    print("indoor_pbf:", indoor_pbf)

    cmd = "osmium export " + indoor_pbf + " " + "--output-format=geojson " + "--add-unique-id=type_id"
    print(cmd)
    with subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE
    ) as proc_export:
        # try:
        indoors = geopandas.read_file(proc_export.stdout)
        if "indoor" not in indoors:
            return
        # except ValueError:
        #     print(traceback.format_exc(), file=sys.stderr)         
        #     return
        # except AttributeError:
        #     print(traceback.format_exc(), file=sys.stderr)         
        #     return

    cmd = "osmium export " + building_pbf + " " + "--output-format=geojson " + "--add-unique-id=type_id"
    print(cmd)
    with subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE
    ) as proc_export:
        try:
            buildings = geopandas.read_file(proc_export.stdout)
        except ValueError:
            print(traceback.format_exc(), file=sys.stderr)         
            return
        except AttributeError:
            print(traceback.format_exc(), file=sys.stderr)         
            return

        # print('Imported:' + gdf.to_json())

    # if ('building' not in building_indoor_gdf) or ('indoor' not in building_indoor_gdf):
    #     return

    # extract buildings

    if buildings.empty:
        return

    # buildings = buildings[buildings['building'].notnull()]
    buildings = buildings[buildings['geometry'].apply(
        lambda shap :
        (
            (
                    shap.geom_type=='LineString'
                    or shap.geom_type=='Polygon'
                ) and len(shap.coords)>2
            ) or (
                shap.geom_type=='MultiLineString'
                or shap.geom_type=='MultiPolygon'                    
            )
        )
    ]
    
    buildings['geometry']=buildings.geometry.apply(
        lambda shap: fix_shap(shap)
    )
    if buildings.empty:
        return
    # buildings = buildings[buildings['geometry'].is_valid]    

    #     buildings['geometry']=buildings.geometry.apply(
    #         lambda shap :
    #             Polygon(mapping(shap)['coordinates']) if ((shap.geom_type=='LineString') and len(shap.coords)>2)
    #             else MultiPolygon(coord for coord in mapping(shap)['coordinates'] if len(coord) > 2) if (shap.geom_type=='MultiLineString' or shap.geom_type=='MultiPolygon')
    #             else shap if (len(shap.coords) > 2)
    #             else None
    #     )
    # try:
    # except:
    #     for index, row in buildings.iterrows():
    #         shap = row['geometry']
    #         print('shap.geom_type:', shap.geom_type)
    #     traceback.print_stack()
    # buildings['geometry'] = buildings['id'].apply(hash, axis=1)

    # buildings.loc[:, 'geometry'] = [
    #     Polygon(mapping(shap)['coordinates'])
    #         if shap.geom_type=='LineString' else
    #             MultiPolygon(coord for coord in mapping(shap)['coordinates'] if len(coord) > 2)
    #                 if (
    #                     shap.geom_type=='MultiLineString'
    #                     or shap.geom_type=='MultiPolygon'
    #                 ) else shap
    #         for shap in buildings.geometry
    # ]

    # buildings.rename(columns={"id":"openindoor_id"},inplace=True)
    # buildings.rename(columns={"id":"openindoor_id"},inplace=True)


    # indoors = building_indoor_gdf[building_indoor_gdf['indoor'].notnull()]
    indoors = indoors[indoors['indoor'].notnull()]


    # # indoors = indoors[indoors['indoor']!='no']
    # indoors = indoors.drop_duplicates(subset=["geometry"]

    print("indoors:", indoors)
    print("buildings:", buildings)

    footprints = buildings[buildings["geometry"].apply(
        lambda shap : inside(shap, indoors)
        )
    ]
    if footprints.empty:
        return

    footprints['region'] = region_name

    # footprints['centroid'] = footprints.centroid
    # centroid = footprints.centroid
    # centroid_ = centroid.to_crs({'init': 'epsg:4326'})

    # footprints['centroid']=footprints["geometry"].centroid
    # print("footprints:", footprints)

    footprints = footprints[footprints.columns.intersection(set([
        "geometry",
        "centroid",
        "region",
        "id",
        "alt_name",
        "amenity",
        "architect",
        "building",
        "building:height",
        "building:levels",
        "building:level",
        "building:max_level",
        "building:part",
        "height",
        "level",
        "maxheight",
        "min_height",
        "min_level",
        "max_level",
        "maxheight",
        "museum",
        "name",
        "region",
        "tourism",
        "shop",
        "wheelchair",
        "wikipedia"
        ]))]

    footprints['centroid']=footprints["geometry"].centroid.apply(
        lambda geom: WKTElement(geom.wkt, srid=4326))

    footprints['geometry']=footprints.geometry.apply(
        lambda geom: WKTElement(geom.wkt, srid=4326))

    # footprints = footprints[
    #     [
    #     "id",
    #     "geometry",
    #     "centroid",
    #     "indoor",
    #     "building",
    #     "building:colour",
    #     "building:levels",
    #     "building:material",
    #     "building:min_level",
    #     "building:part",
    #     "height",
    #     "level",
    #     "min_height",
    #     "max_height",
    #     "name",
    #     "source",
    #     "type",
    #     "wheelchair",
    #     ]
    # ]
    # buildings.to_json()
    footprints.to_sql(
        name = "footprint",
        con = engine,
        if_exists = 'append',
        index = False,
        # dtype = {'geometry': Geometry(geometry_type='POLYGON', srid=4326)},
        dtype = {
            'geometry': Geometry(),
            'centroid': Geometry(geometry_type='POINT', srid=4326)
        },
        method = upsert
    )

def pbf_extractor(region):
    print("Going to process:", region)
    region_name=region["name"]
    region_poly=region["poly"]
    region_pbf=region["pbf"]
    poly_file = "/data/" + region_name + ".poly"
    pbf_file = "/data/" + region_name + ".osm.pbf"
    if not os.path.isfile(poly_file):
        print("download: " + poly_file)
        wget.download(region_poly, poly_file)
    print("File found: " + poly_file)
    if not os.path.isfile(pbf_file):
        print("download: " + region_pbf)
        wget.download(region_pbf, pbf_file)
    print("File found: " + pbf_file)

    # now = datetime.now()
    # dt_string = now.strftime("%Y%m%d_%H%M%S")
    # pbf_file_out = os.path.dirname(pbf_file)  + '/' + dt_string + '_' + os.path.basename(pbf_file)
    # print('pbf_file_out: ' + pbf_file_out)
    # cmd = [
    #     "osmupdate", "-v",
    #     pbf_file,
    #     pbf_file_out,
    #     "-B=" + poly_file
    # ]

    # print(cmd)
    # building_indoor_filter = subprocess.run(cmd)
    # os.remove(pbf_file)
    # os.rename(pbf_file_out, pbf_file)

    os.makedirs("/data/tmp/" + region_name, exist_ok=True)
    indoor_pbf = "/data/tmp/" + region_name + "/indoor.osm.pbf"
    building_pbf = "/data/tmp/" + region_name + "/building.osm.pbf"
    cmd_indoor = [
        "osmium",
        "tags-filter",
        "--progress",
        "--overwrite",
        "--output-format=pbf",
        "--fsync",
        "--output=" + indoor_pbf,
        pbf_file,
        "w/indoor"
    ]
    cmd_building = [
        "osmium",
        "tags-filter",
        "--progress",
        "--overwrite",
        "--output-format=pbf",
        "--fsync",
        "--output=" + building_pbf,
        pbf_file,
        "w/building", "w/building:part",
        "a/building", "a/museum"
    ]
    print(cmd_indoor)
    indoor_filter = subprocess.run(cmd_indoor)
    print("size of " + indoor_pbf + ": " + str(os.path.getsize(indoor_pbf)))
    print(cmd_building)
    building_filter = subprocess.run(cmd_building)
    print("size of " + building_pbf + ": " + str(os.path.getsize(building_pbf)))
    splitter(
        indoor_pbf=indoor_pbf,
        building_pbf=building_pbf,
        max_zoom=18,
        min_zoom=15,
        region_name=region_name,
        bbox={
            "zoom": 1,
            "xmin": 0, "ymin": 0,
            "xmax": 1, "ymax": 1,
        },
        # Centroid issue
        # bbox={
        #     "zoom": 18,
        #     "xmin": 132701, "ymin": 90145,
        #     "xmax": 132702, "ymax": 90146,
        # },
        # bbox={
        #     "zoom": 7,
        #     "xmin": 64, "ymin": 42,
        #     "xmax": 65, "ymax": 43,
        # },
        # bbox={
        #     "zoom": 11,
        #     "xmin": 1032, "ymin": 702,
        #     "xmax": 1033, "ymax": 703,
        # },
        # bbox={
        #     "zoom": 15,
        #     "xmin": 16538, "ymin": 11254,
        #     "xmax": 16539, "ymax": 11255,
        # },
        method=process_tile
    )

def main():
    print("Starting process...")
    with open('regions.json') as regions:
        region_data = json.load(regions)
    for region in region_data['regions']:
        pbf_extractor(region)

if __name__ == "__main__":
    main()

