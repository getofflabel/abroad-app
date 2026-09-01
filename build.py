#!/usr/bin/env python3
"""Build the published site into ./public.

  public/index.html      the shareable demo (no login, in-memory data)
  public/app/index.html  the real app (.edu sign-in, live Supabase)

Run `python3 build.py` locally, or let the GitHub Action do it on every push.
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src')
OUT = os.path.join(ROOT, 'public')


def inline_places(html):
    """Bake places.json into the page so city pages work with no runtime fetch."""
    path = os.path.join(SRC, 'places.json')
    if not os.path.exists(path):
        print('WARNING: no places.json, city pages will have no suggestions')
        return html
    blob = open(path).read().strip()
    tag = '<script>window.PLACES=%s;</script>\n' % blob
    marker = '<script>window.IMG='
    i = html.index(marker)
    print('  places.json inlined (%.0f KB)' % (len(blob) / 1024))
    return html[:i] + tag + html[i:]


def run(script):
    subprocess.run([sys.executable, script], cwd=SRC, check=True)


def main():
    run('build.py')        # src/abroad.code.html + img_line.txt -> abroad.html
    run('build_demo.py')   # abroad.html -> abroad.demo.html

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'app'))

    shutil.copy(os.path.join(ROOT, 'share_card.jpg'), os.path.join(OUT, 'share_card.jpg'))
    shutil.copy(os.path.join(ROOT, 'site.webmanifest'), os.path.join(OUT, 'site.webmanifest'))
    shutil.copytree(os.path.join(ROOT, 'icons'), os.path.join(OUT, 'icons'))
    for src_name, dest in (('abroad.demo.html', os.path.join(OUT, 'index.html')),
                           ('abroad.html', os.path.join(OUT, 'app', 'index.html'))):
        open(dest, 'w').write(inline_places(open(os.path.join(SRC, src_name)).read()))

    for name, path in (('demo', os.path.join(OUT, 'index.html')),
                       ('app', os.path.join(OUT, 'app', 'index.html'))):
        print('%-5s %6.0f KB  %s' % (name, os.path.getsize(path) / 1024, path))


if __name__ == '__main__':
    main()
