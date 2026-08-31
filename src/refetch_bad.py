#!/usr/bin/env python3
"""Re-source city photos that came back as maps, flags, coats of arms or
collages, by searching Wikimedia Commons for a real landscape photograph.
"""
import json, os, re, sys, urllib.parse, urllib.request
from PIL import Image

P = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(P, 'city_src')
UA = {'User-Agent': 'AbroadApp/1.0 (+https://github.com/getofflabel/abroad-app)'}

BAD = re.compile(r'flag|map|locator|coat[_ ]of[_ ]arms|montage|collage|seal|'
                 r'emblem|banner|logo|\.svg|location|orthographic|globe|'
                 r'astronaut|satellite|from space|landsat|sentinel',
                 re.I)


def get(u, t=40):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()


def commons_search(query, limit=30):
    u = ('https://commons.wikimedia.org/w/api.php?action=query&generator=search'
         '&gsrsearch=' + urllib.parse.quote(query) +
         '&gsrnamespace=6&gsrlimit=%d&prop=imageinfo'
         '&iiprop=url|size|extmetadata&iiurlwidth=2000&format=json' % limit)
    d = json.loads(get(u))
    out = []
    for pg in (d.get('query', {}).get('pages', {}) or {}).values():
        ii = (pg.get('imageinfo') or [{}])[0]
        title = pg.get('title', '')
        if BAD.search(title):
            continue
        w, h = ii.get('width', 0), ii.get('height', 0)
        if w < 1500 or h == 0 or w / h < 1.2:      # want wide, high-res photos
            continue
        m = ii.get('extmetadata', {})
        def f(k):
            return re.sub(r'<[^>]+>', '', m.get(k, {}).get('value', '')).strip()
        out.append({'title': title, 'url': ii.get('url'), 'w': w, 'h': h,
                    'author': f('Artist'), 'license': f('LicenseShortName')})
    out.sort(key=lambda r: -r['w'])
    return out


QUERIES = {
    'bali':       'Bali Indonesia rice terrace landscape',
    'hong-kong':  'Hong Kong skyline Victoria Harbour night',
    'singapore':  'Singapore skyline Marina Bay',
    'mykonos':    'Mykonos Chora windmills town',
    'santorini':  'Santorini Oia village sunset',
    'san-jose':   'San Jose Costa Rica downtown street architecture',
    'los-angeles': 'Los Angeles downtown skyline sunset',
}


def looks_like_photo(path):
    """Flags and maps have very few distinct colours; photos have thousands."""
    im = Image.open(path).convert('RGB').resize((160, 120))
    return len(set(im.getdata())) > 4000


if __name__ == '__main__':
    targets = sys.argv[1:] or list(QUERIES)
    creds = {}
    for slug in targets:
        q = QUERIES.get(slug, slug.replace('-', ' ') + ' city skyline')
        try:
            hits = commons_search(q)
        except Exception as e:
            print('%-12s search failed: %s' % (slug, e)); continue
        placed = False
        for h in hits[:8]:
            try:
                data = get(h['url'])
                tmp = os.path.join(SRC, slug + '.jpg')
                open(tmp, 'wb').write(data)
                if not looks_like_photo(tmp):
                    print('%-12s rejected (not a photo): %s' % (slug, h['title'][:50]))
                    continue
                json.dump({'file': h['title'], 'author': h['author'],
                           'license': h['license']},
                          open(os.path.join(SRC, slug + '.json'), 'w'))
                print('%-12s OK  %sx%s  %s' % (slug, h['w'], h['h'], h['title'][:52]))
                creds[slug] = h
                placed = True
                break
            except Exception as e:
                print('%-12s fetch failed: %s' % (slug, e))
        if not placed:
            print('%-12s *** NO REPLACEMENT FOUND ***' % slug)
