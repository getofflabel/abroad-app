#!/usr/bin/env python3
"""Build abroad.html (shippable) and abroad.sim.html (simulator, pre-signed-in)
from abroad.code.html + img_line.txt.

img_line.txt holds the ENTIRE <script>window.IMG={...};</script> line, so the
whole placeholder line in abroad.code.html gets swapped out for it. Replacing
just the __IMG__ token would nest one script tag inside another.
"""
import json, os, sys

P = os.path.dirname(os.path.abspath(__file__))
code = open(os.path.join(P, 'abroad.code.html')).read().split('\n')
img = open(os.path.join(P, 'img_line.txt')).read().strip()

hits = [i for i, l in enumerate(code) if '__IMG__' in l]
assert len(hits) == 1, 'expected exactly one __IMG__ line, got %d' % len(hits)
code[hits[0]] = img
html = '\n'.join(code)

# sanity: no nested script tags in the IMG blob
s = html.index('<script>window.IMG=')
e = html.index('</script>', s) + len('</script>')
assert '<script' not in html[s + 8:e - 9], 'nested script tag in IMG line'
assert html[e:e + 9] != ';</script>', 'leftover placeholder tail'

open(os.path.join(P, 'abroad.html'), 'w').write(html)

# The simulator copy is only for local device testing and needs a live session
# file. CI has none, and the published site never uses it, so stop here.
if not os.path.exists(os.path.join(P, 'demo_session.json')):
    print('built abroad.html (%d bytes); no demo_session.json, skipped sim copy' % len(html))
    raise SystemExit(0)

# Simulator copy: seed the demo session so the app opens signed in.
# Must match the shape the app itself stores (user_id at the top level, ms
# expiry) or loadSession() rejects it and drops you back on the welcome screen.
raw = json.load(open(os.path.join(P, 'demo_session.json')))
sess = {
    'access_token': raw['access_token'],
    'refresh_token': raw['refresh_token'],
    'expires_at': raw['expires_at'] * 1000,
    'user_id': raw['user']['id'],
    'email': raw['user']['email'],
}
boot = ('<script>try{localStorage.setItem("abroad_session",%s);}catch(e){}</script>'
        % json.dumps(json.dumps(sess)))
open(os.path.join(P, 'abroad.sim.html'), 'w').write(html[:e] + '\n' + boot + html[e:])

print('built abroad.html (%d bytes) + abroad.sim.html' % len(html))
