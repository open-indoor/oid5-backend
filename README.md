# oid5-backend
indoor data extractor and provider

# Data type
## "places" table
Building footprints

## "buildings" table
All indoor data (with buildings)

## "pins" table
Calculate the centroïd of all buildings

# Process
1 - get osm.pbf
The current osm.pbf contains "buildings:levels" and "indoor:*" data

2 - Filter all buildings that contains indoor data
-> osm.pbf -> geojson (osmium)
-> load geojson data in geopandas with python/geopandas
-> use within() / contains() / intersect()
-> output to geojson
-> send to DB

 - export to geojson
 - import in db

# Test / validation

```
ogr2ogr -f "PostgreSQL" \
  PG:"dbname='openindoor-db' host='openindoor-db' port='5432' user='openindoor-db-admin' password='admin123'" \
  /test/data/Rennes_example.geojson \
  -nln buildings \
  -overwrite \
  -skipfailures
```

```
ogr2ogr -f "PostgreSQL" \
  PG:"dbname='openindoor-db' host='openindoor-db' port='5432' user='openindoor-db-admin' password='admin123'" \
  /data/tmppoly.geojson \
  -nln "building_footprint" \
  -overwrite \
  -skipfailures
```