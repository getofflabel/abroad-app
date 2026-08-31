# Abroad

Weekend trips with people from your study-abroad program.

## What deploys

| URL | What it is |
| --- | --- |
| `/` | **Demo.** No login. Runs on a frozen snapshot, in memory. Safe to share with anyone: it cannot reach the live database and nothing anyone does is saved. |
| `/app` | **The real app.** `.edu` sign-in, live Supabase. |

## Layout

    src/abroad.code.html   the app, with an __IMG__ placeholder for the photo blob
    src/img_line.txt       base64 photos for the 7 hero cities (one long line)
    src/build.py           code + photos -> abroad.html
    src/build_demo.py      abroad.html -> abroad.demo.html (in-memory data layer)
    src/demo_snapshot.json data the demo is seeded from
    src/city_photos.py     re-fetch + grade city photos from Wikimedia
    src/grade.py           the one shared dusk grade every photo goes through
    build.py               builds both into public/

Edit `src/abroad.code.html`, never `public/`. Run `python3 build.py`, push, and
the deploy picks it up. Never hand-replace `__IMG__` (it nests script tags).

## Refreshing the demo data

Re-snapshot from Supabase into `src/demo_snapshot.json`, then rebuild. The extra
trips in the demo are hosted by real accounts; no students are invented.
