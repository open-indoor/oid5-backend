################ PLACES #####################
FROM fedora:rawhide

RUN dnf -y upgrade \
    && dnf -y install \
      bash \
      cronie \
      curl \
      file \
      gettext \
      git \
      grep \
      htop \
      jq \
      less \
      net-tools \
      nmap \
      osmium-tool \
      procps-ng \
      unzip \
      util-linux \
      uuid \
      vim \
      wget \
    && dnf -y clean all

RUN dnf -y install \
      gdal \
      osmctools \
      postgresql \
      python3-wheel \
      python3-geopandas \
      python3-geojson \
      python3-pycurl \
      python3-pip \
      python3-rtree \
      python3-requests \
      python3-flask \
      python3-sqlalchemy \
      python3-psycopg2 \ 
      python3-socketio \
    && dnf -q clean all

RUN mkdir -p /places-finder
COPY ./requirements.txt /places-finder/
RUN pip3 install -r /places-finder/requirements.txt

# COPY ./Caddyfile /etc/caddy/Caddyfile

WORKDIR /places-finder

COPY ./places-finder.py /places-finder/places-finder.py
COPY ./regions.json /places-finder/regions.json
RUN chmod +x /places-finder/places-finder.py

RUN mkdir -p /data/tmp

CMD bash -c "/places-finder/places-finder.py"