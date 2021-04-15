# oid5-backend
indoor data extractor and provider



# Process
1 - get osm.pbf
2 - export to geojson
3 - import in db

# Test / validation

```
ogr2ogr -f "PostgreSQL" \
  PG:"dbname='openindoor-db' host='openindoor-db' port='5432' user='openindoor-db-admin' password='admin123'" \
  /test/data/Rennes_example.geojson \
  -nln buildings \
  -overwrite \
  -skipfailures
```
