#!/usr/bin/env python3
"""Build abroad.demo.html — a shareable, no-login demo of the app.

Anyone who opens the real build hits the .edu sign-in wall, so it can't be sent
to anyone. This variant swaps the single network choke point (DB._req) for an
in-memory store seeded from a snapshot of the real data, and stubs photo upload.
Nothing it does can reach the live database, and it never expires.
"""
import json, os, re

P = os.path.dirname(os.path.abspath(__file__))
snap = json.load(open(os.path.join(P, 'demo_snapshot.json')))
ME = snap['me']

# The snapshot only has two trips, which makes the feed look dead. Extra trips
# are hosted by the two people who already exist -- no invented students.
profiles = snap['abroad_profiles']
other = next((p['id'] for p in profiles if p['id'] != ME), ME)

EXTRA = [
    ('porto',    'Porto',    'Portugal', 'Port tasting and the Gaia sunset',        '2026-09-04', '2026-09-06', 4, other),
    ('seville',  'Seville',  'Spain',    'Flamenco night in Triana',                '2026-09-18', '2026-09-20', 6, ME),
    ('barcelona','Barcelona','Spain',    'Beach day then Gothic Quarter tapas',     '2026-09-25', '2026-09-27', 4, other),
    ('budapest', 'Budapest', 'Hungary',  'Thermal baths and ruin bars',             '2026-10-09', '2026-10-11', 6, ME),
]
for i, (slug, city, country, title, s, e, cap, host) in enumerate(EXTRA):
    tid = 'demo-trip-%d' % i
    snap['abroad_trips'].append({
        'id': tid, 'host_id': host, 'city_slug': slug, 'city_name': city,
        'country': country, 'title': title, 'starts_on': s, 'ends_on': e,
        'capacity': cap, 'status': 'open', 'cover_key': None,
        'created_at': '2026-08-%02dT12:00:00+00:00' % (20 + i),
    })
    snap['abroad_trip_members'].append({
        'trip_id': tid, 'profile_id': host, 'role': 'host',
        'status': 'accepted', 'created_at': '2026-08-%02dT12:00:00+00:00' % (20 + i),
    })

SNAP_JS = json.dumps(snap, separators=(',', ':'))

DEMO_JS = """
<script>
/* ---------------- DEMO MODE ----------------
   A self-contained, shareable build. DB._req below is a small in-memory stand-in
   for PostgREST: it serves the seeded snapshot and applies writes to memory only,
   so the demo can never touch the live database and never needs a login. */
window.ABROAD_DEMO = %s;
</script>
""" % SNAP_JS

# Replacement for the networked _req. Same signature, same promise contract.
FAKE_REQ = """    _req: function(method, table, query, body, extraHeaders){
      /* DEMO: in-memory stand-in for PostgREST. Serves the seeded snapshot and
         keeps writes local, so nothing here can reach the real database. */
      var DB_MEM = window.__MEM__;
      var rows = DB_MEM[table] || (DB_MEM[table] = []);
      var q = String(query || '').replace(/^\\?/, '');
      var parts = q ? q.split('&') : [];
      var filters = [], order = null, limit = null, upsert = /merge-duplicates/.test(
        (extraHeaders && extraHeaders.Prefer) || '');
      var minimal = /return=minimal/.test((extraHeaders && extraHeaders.Prefer) || '');
      parts.forEach(function(part){
        var eq = part.indexOf('=');
        if(eq === -1) return;
        var key = part.slice(0, eq), val = part.slice(eq + 1);
        if(key === 'select' || key === 'on_conflict') return;
        if(key === 'order'){ order = val.split('.'); return; }
        if(key === 'limit'){ limit = parseInt(val, 10); return; }
        if(val.indexOf('eq.') === 0) filters.push({k:key, op:'eq', v:decodeURIComponent(val.slice(3))});
        else if(val.indexOf('in.') === 0) filters.push({k:key, op:'in',
          v:decodeURIComponent(val.slice(3)).replace(/^\\(|\\)$/g,'').split(',').filter(Boolean)});
        else if(val.indexOf('is.') === 0) filters.push({k:key, op:'is', v:val.slice(3)});
      });
      function match(r){
        return filters.every(function(f){
          var cell = r[f.k];
          if(f.op === 'eq') return String(cell) === String(f.v) ||
            (f.v === 'true' && cell === true) || (f.v === 'false' && cell === false);
          if(f.op === 'in') return f.v.indexOf(String(cell)) !== -1;
          if(f.op === 'is') return f.v === 'null' ? (cell === null || cell === undefined) : true;
          return true;
        });
      }
      function done(v){ return new Promise(function(res){ setTimeout(function(){ res(v); }, 60); }); }
      var out;
      if(method === 'GET'){
        out = rows.filter(match);
        if(order){
          var key = order[0], dir = order[1] === 'desc' ? -1 : 1;
          out = out.slice().sort(function(a,b){
            var x=a[key], y=b[key];
            if(x===y) return 0;
            return (x>y?1:-1)*dir;
          });
        }
        if(limit) out = out.slice(0, limit);
        return done(out);
      }
      if(method === 'POST'){
        var incoming = Array.isArray(body) ? body : [body];
        var saved = incoming.map(function(row){
          var rec = JSON.parse(JSON.stringify(row));
          if(upsert && rec.id){
            var existing = rows.filter(function(r){ return r.id === rec.id; })[0];
            if(existing){ for(var k in rec) existing[k] = rec[k]; return existing; }
          }
          if(!rec.id) rec.id = 'demo-' + Math.random().toString(36).slice(2, 11);
          if(!rec.created_at) rec.created_at = new Date().toISOString();
          rows.push(rec);
          /* mirror the server trigger that seats the host on their own trip */
          if(table === 'abroad_trips'){
            (DB_MEM.abroad_trip_members = DB_MEM.abroad_trip_members || []).push({
              trip_id: rec.id, profile_id: rec.host_id, role: 'host',
              status: 'accepted', created_at: rec.created_at });
          }
          return rec;
        });
        return done(minimal ? null : saved);
      }
      if(method === 'PATCH'){
        var hit = rows.filter(match);
        hit.forEach(function(r){ for(var k in body) r[k] = body[k]; });
        return done(minimal ? null : hit);
      }
      if(method === 'DELETE'){
        for(var i = rows.length - 1; i >= 0; i--) if(match(rows[i])) rows.splice(i, 1);
        return done(null);
      }
      return done(null);
    },"""


def build():
    html = open(os.path.join(P, 'abroad.html')).read()

    # 1. swap the network layer for the in-memory one
    start = html.index('    _req: function(method, table, query, body, extraHeaders, retried){')
    end = html.index('    select: function(table, query){', start)
    html = html[:start] + FAKE_REQ + '\n' + html[end:]

    # 2. photo upload has no server here; hand back a local object URL
    start = html.index('  function uploadPhotoFile(file){')
    end = html.index('  window.uploadPhotoFile = uploadPhotoFile;', start)
    html = html[:start] + (
        "  function uploadPhotoFile(file){\n"
        "    /* DEMO: keep the picked photo in the page instead of uploading it. */\n"
        "    if(!file) return Promise.reject(new Error('No file'));\n"
        "    var url = URL.createObjectURL(file);\n"
        "    window.__BLOBS__[url] = 1;\n"
        "    return Promise.resolve(url);\n"
        "  }\n") + html[end:]

    # 3. a local blob url must not be rewritten into a storage path
    html = html.replace(
        "    if(/^https?:\\/\\//.test(key)) return key;",
        "    if(/^(https?:|blob:)/.test(key)) return key;")

    # 4. seed the store and drop straight into the app, no sign-in
    boot = ("<script>(function(){\n"
            "  var S = window.ABROAD_DEMO;\n"
            "  window.__MEM__ = S; window.__BLOBS__ = {};\n"
            "  try{ localStorage.setItem('abroad_session', JSON.stringify({\n"
            "    access_token:'demo', refresh_token:'demo',\n"
            "    expires_at: Date.now() + 3155760000000, user_id: S.me,\n"
            "    email:'demo@student.edu' })); }catch(e){}\n"
            "})();</script>\n")

    marker = '<script>window.IMG='
    i = html.index(marker)
    j = html.index('</script>', i) + len('</script>')
    html = html[:j] + '\n' + DEMO_JS + boot + html[j:]

    # distinct <title> so the demo is easy to tell apart from the real build
    html = html.replace('<title>Abroad</title>', '<title>Abroad Demo</title>', 1)

    out = os.path.join(P, 'abroad.demo.html')
    open(out, 'w').write(html)
    print('built abroad.demo.html (%d bytes, %d trips, %d profiles)'
          % (len(html), len(snap['abroad_trips']), len(snap['abroad_profiles'])))


if __name__ == '__main__':
    build()
