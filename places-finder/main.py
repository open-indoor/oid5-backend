#!/usr/bin/python3
import os
import subprocess
from flask import Flask
import getData

import requests
import json
from urllib.request import Request, urlopen, urlretrieve


app = Flask(__name__)

@app.route("/", methods=['GET',])
def bla():
    # subprocess.run("python3 /places-finder/getData.py")
    # dowloadDest = getData.download()
    # print("yo")
    # with open('./regions.json') as regionsFile:
    #     data = json.load(regionsFile)
    #     regionsData = data["regions"][0]
    #     url = regionsData["html_page"]
    # requester
    # req = Request(url)
    r = requests.get('https://download.geofabrik.de/europe/france.html')
    # # Page openning
    # html_page = urlopen(r)
    # print("dd :" + ''.join(dowloadDest))
    return r.url


@app.route("/scode", methods=['GET',])
def bla2():
    r = requests.get('https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Accueil_principal')
    return str(r.status_code)

@app.route("/content", methods=['GET',])
def bla3():
    r = requests.get('https://fr.wikipedia.org/wiki/Wikip%C3%A9dia:Accueil_principal',
    timeout=15)
    return r.content



if __name__ == "__main__":
        print("yo1")
        port = int(os.environ.get("PORT",80))
        app.run(debug=True,host='0.0.0.0',port=port)