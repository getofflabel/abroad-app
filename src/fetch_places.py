#!/usr/bin/env python3
"""Pull real places for every popular city from OpenStreetMap into places.json.

Nothing here is written by us. Every entry is a real, named, mapped place with
coordinates, so the city pages can suggest things to do without inventing them.
Overpass is rate limited, so this runs slowly and on purpose; it is a build step,
not something the app calls at runtime.
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

P = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'AbroadApp/1.0 (+https://github.com/getofflabel/abroad-app)'}
ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
]

# Categories in the students' words, mapped to what OSM actually tags.
CATS = {
    'sights':    ['node(area.a)["tourism"="attraction"]["name"]["wikidata"];',
                  'node(area.a)["tourism"="viewpoint"]["name"];',
                  'way(area.a)["historic"~"castle|monument|memorial"]["name"]["wikidata"];'],
    'nightlife': ['node(area.a)["amenity"="nightclub"]["name"];',
                  'node(area.a)["amenity"="bar"]["name"]["website"];'],
    'museums':   ['node(area.a)["tourism"="museum"]["name"];',
                  'way(area.a)["tourism"="museum"]["name"];',
                  'node(area.a)["tourism"="gallery"]["name"];'],
    'food':      ['node(area.a)["amenity"="marketplace"]["name"];',
                  'node(area.a)["amenity"="cafe"]["name"]["website"];',
                  'node(area.a)["amenity"="restaurant"]["name"]["website"];'],
    'outdoors':  ['node(area.a)["natural"="beach"]["name"];',
                  'way(area.a)["natural"="beach"]["name"];',
                  'way(area.a)["leisure"="park"]["name"]["wikidata"];',
                  'node(area.a)["natural"="peak"]["name"]["wikidata"];'],
}
PER_CAT = 8


def slug(name):
    s = unicodedata.normalize('NFD', name)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def query(city, cat):
    body = '\n  '.join(CATS[cat])
    return ('[out:json][timeout:50];\n'
            'area["name"="%s"]["boundary"="administrative"]["admin_level"~"4|6|7|8"]->.a;\n'
            '(\n  %s\n);\nout center tags %d;' % (city, body, PER_CAT * 4))


def run(q, attempt=0):
    url = ENDPOINTS[attempt % len(ENDPOINTS)]
    req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(),
                                 headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


def clean(els):
    seen, out = set(), []
    for e in els:
        t = e.get('tags') or {}
        name = (t.get('name') or '').strip()
        if not name or len(name) > 48 or name.lower() in seen:
            continue
        lat = e.get('lat') or (e.get('center') or {}).get('lat')
        lon = e.get('lon') or (e.get('center') or {}).get('lon')
        if lat is None or lon is None:
            continue
        kind = (t.get('tourism') or t.get('amenity') or t.get('natural')
                or t.get('historic') or t.get('leisure') or '')
        seen.add(name.lower())
        # notable first: a wikidata tag means the place has a real entry
        out.append({'n': name, 'k': kind, 'lat': round(lat, 5), 'lon': round(lon, 5),
                    'w': 1 if t.get('wikidata') else 0})
    out.sort(key=lambda r: (-r['w'], r['n']))
    for r in out:
        r.pop('w', None)
    return out[:PER_CAT]


def city_places(city):
    got = {}
    for cat in CATS:
        for attempt in range(3):
            try:
                d = run(query(city, cat), attempt)
                rows = clean(d.get('elements', []))
                if rows:
                    got[cat] = rows
                break
            except Exception:
                time.sleep(4 + attempt * 6)
        time.sleep(1.5)
    return city, got


if __name__ == '__main__':
    cities = [c['n'] for c in json.load(open(os.path.join(P, 'cities.json'))) if c.get('p')]
    if len(sys.argv) > 1:
        cities = cities[:int(sys.argv[1])]

    out_path = os.path.join(P, 'places.json')
    places = json.load(open(out_path)) if os.path.exists(out_path) else {}

    todo = [c for c in cities if slug(c) not in places]
    print('%d cities, %d already done, fetching %d' % (len(cities), len(cities) - len(todo), len(todo)))

    done = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for city, got in ex.map(city_places, todo):
            done += 1
            if got:
                places[slug(city)] = got
            n = sum(len(v) for v in got.values())
            print('%3d/%-3d %-16s %3d places  %s' % (done, len(todo), city, n,
                                                     ','.join(sorted(got))), flush=True)
            json.dump(places, open(out_path, 'w'), separators=(',', ':'))

    total = sum(len(v) for c in places.values() for v in c.values())
    print('\n%d cities, %d places, %.0f KB'
          % (len(places), total, os.path.getsize(out_path) / 1024))
