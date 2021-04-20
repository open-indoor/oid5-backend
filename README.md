# OID5-BACKEND 

> The env_v1 branch provides a first clean env. This environment allow you to render gemotric data tahnks to tegola.

This exemple is based on 4 french regions. The corresponding geometric data files are take from geofabirk.ge. Thoses data are load in a postgis db which are accessible with adminer (port 8091). The graphic result is visible from tegola (port 8092).

## Basic usage

```dokcer-compose up --build```

## Usage with your data

### Data from geofabrik 

If you want to change the data, you have to change the regions.json file according to his current architecture.

### Other data

You moght rewrite the getData.py script and the config.toml cinfiguration file according to your needs.