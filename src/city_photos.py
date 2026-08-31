#!/usr/bin/env python3
"""Fetch a lead photo for every popular Abroad city from Wikimedia, apply the
one shared Abroad dusk grade, and write graded JPEGs + an attribution manifest.

Every photo goes through the SAME grade so the app looks like one photographer
shot it. Ungraded mixed-source stock is the #1 "this looks AI" tell.
"""
import json, os, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageEnhance

P = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(P, 'city_src')
GRADED = os.path.join(P, 'city_graded')
UA = {'User-Agent': 'AbroadApp/1.0 (+https://github.com/getofflabel/abroad-app)'}

# Wikipedia article titles where the bare city name is ambiguous or wrong.
TITLE = {
    'Nice': 'Nice', 'Split': 'Split, Croatia', 'Santiago': 'Santiago',
    'San José': 'San José, Costa Rica', 'Valencia': 'Valencia',
    'Granada': 'Granada', 'New York': 'New York City', 'Bali': 'Bali',
    'Cusco': 'Cusco', 'Porto': 'Porto', 'Milan': 'Milan', 'Munich': 'Munich',
    'Vienna': 'Vienna', 'Venice': 'Venice', 'Florence': 'Florence',
    'Athens': 'Athens', 'Cairo': 'Cairo', 'Lima': 'Lima', 'Oslo': 'Oslo',
    'Seoul': 'Seoul', 'Tulum': 'Tulum', 'Mykonos': 'Mykonos',
    'Santorini': 'Santorini', 'Bruges': 'Bruges', 'Interlaken': 'Interlaken',
    'Queenstown': 'Queenstown, New Zealand', 'Reykjavik': 'Reykjavík',
    'Marrakesh': 'Marrakesh', 'Bogotá': 'Bogotá', 'Medellín': 'Medellín',
    'Cartagena': 'Cartagena, Colombia', 'Mexico City': 'Mexico City',
    'Rio de Janeiro': 'Rio de Janeiro', 'Buenos Aires': 'Buenos Aires',
    'Cape Town': 'Cape Town', 'Hong Kong': 'Hong Kong',
    'Los Angeles': 'Los Angeles', 'Montreal': 'Montreal',
}


def slug(name):
    s = name.lower()
    s = s.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    s = s.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    s = s.replace('å', 'a').replace('ö', 'o').replace('ø', 'o')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def get(url, timeout=40):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read()


def lead_image(city):
    """Return (image_url, wiki_page_url) for a city, or None."""
    title = TITLE.get(city, city)
    api = ('https://en.wikipedia.org/api/rest_v1/page/summary/'
           + urllib.parse.quote(title.replace(' ', '_')))
    d = json.loads(get(api))
    src = (d.get('originalimage') or {}).get('source')
    if not src:
        return None
    page = (d.get('content_urls', {}).get('desktop', {}) or {}).get('page', '')
    return src.split('?')[0], page


def commons_credit(img_url):
    """Look up author + license for a Commons file so we can credit it."""
    fname = urllib.parse.unquote(img_url.rsplit('/', 1)[-1])
    api = ('https://commons.wikimedia.org/w/api.php?action=query&titles='
           + urllib.parse.quote('File:' + fname)
           + '&prop=imageinfo&iiprop=extmetadata&format=json')
    try:
        d = json.loads(get(api, 20))
        pg = next(iter(d['query']['pages'].values()))
        m = pg['imageinfo'][0]['extmetadata']
        def f(k):
            v = m.get(k, {}).get('value', '')
            return re.sub(r'<[^>]+>', '', v).strip()
        return {'file': fname, 'author': f('Artist'),
                'license': f('LicenseShortName')}
    except Exception:
        return {'file': fname, 'author': '', 'license': ''}


def grade(src_path, dst_path, w=1100, ratio=4 / 3):
    """The one shared Abroad grade: cooled-desat base, warm shift, gentle contrast."""
    im = Image.open(src_path).convert('RGB')

    # centre crop to a consistent aspect so the grid never looks ragged
    tw, th = im.width, int(im.width / ratio)
    if th > im.height:
        th, tw = im.height, int(im.height * ratio)
    im = im.crop(((im.width - tw) // 2, int((im.height - th) * 0.42),
                  (im.width - tw) // 2 + tw, int((im.height - th) * 0.42) + th))
    im = im.resize((w, int(w / ratio)), Image.LANCZOS)

    im = ImageEnhance.Color(im).enhance(0.88)      # desaturate
    im = ImageEnhance.Contrast(im).enhance(1.06)   # slight contrast
    im = ImageEnhance.Brightness(im).enhance(0.94)  # pull down toward dusk

    # warm shift: lift R, hold G, drop B
    r, g, b = im.split()
    r = r.point(lambda v: min(255, int(v * 1.05 + 4)))
    b = b.point(lambda v: max(0, int(v * 0.94 - 2)))
    im = Image.merge('RGB', (r, g, b))

    im.save(dst_path, 'JPEG', quality=76, optimize=True, progressive=True)
    return os.path.getsize(dst_path)


def handle(city):
    sl = slug(city)
    raw = os.path.join(OUT, sl + '.jpg')
    out = os.path.join(GRADED, sl + '.jpg')
    try:
        if not os.path.exists(raw):
            hit = lead_image(city)
            if not hit:
                return (city, sl, None, 'no lead image')
            url, _ = hit
            open(raw, 'wb').write(get(url))
            cred = commons_credit(url)
            json.dump(cred, open(os.path.join(OUT, sl + '.json'), 'w'))
        size = grade(raw, out)
        cred = json.load(open(os.path.join(OUT, sl + '.json')))
        return (city, sl, size, cred)
    except Exception as e:
        return (city, sl, None, '%s: %s' % (type(e).__name__, e))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(GRADED, exist_ok=True)
    cities = [c['n'] for c in json.load(open(os.path.join(P, 'cities.json')))
              if c.get('p')]
    if len(sys.argv) > 1:
        cities = cities[:int(sys.argv[1])]

    manifest, failed = {}, []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for city, sl, size, info in ex.map(handle, cities):
            if size is None:
                failed.append((city, info))
                print('FAIL %-16s %s' % (city, info))
            else:
                manifest[sl] = {'city': city, 'bytes': size, 'credit': info}
                print('ok   %-16s %5.1f KB' % (city, size / 1024))

    json.dump(manifest, open(os.path.join(P, 'city_manifest.json'), 'w'), indent=1)
    total = sum(v['bytes'] for v in manifest.values())
    print('\n%d ok, %d failed, %.1f MB total'
          % (len(manifest), len(failed), total / 1024 / 1024))
