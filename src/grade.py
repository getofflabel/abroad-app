#!/usr/bin/env python3
"""The one shared Abroad dusk grade.

Every photo in the app runs through this and only this. Mixed-source stock in
mixed light is the strongest "AI-generated" tell there is; one grade across
every image is what makes it read like one photographer shot the whole app.

Recipe: desaturate hard, split-tone (cool shadows / amber highlights), lay a
warm-to-indigo vertical wash over the top, deepen contrast, vignette.
"""
import numpy as np
from PIL import Image

SHADOW = np.array([28, 36, 52], dtype=np.float32)    # cool navy in the darks
HIGHLIGHT = np.array([255, 226, 186], dtype=np.float32)  # amber in the brights
SKY = np.array([232, 168, 104], dtype=np.float32)    # warm wash, top of frame
GROUND = np.array([38, 44, 66], dtype=np.float32)    # indigo wash, bottom


def grade(im, ratio=4 / 3, w=900, focus=0.42):
    """Crop, resize and apply the Abroad grade. Returns a PIL image."""
    im = im.convert('RGB')

    tw, th = im.width, int(im.width / ratio)
    if th > im.height:
        th, tw = im.height, int(im.height * ratio)
    x0 = (im.width - tw) // 2
    y0 = int((im.height - th) * focus)
    im = im.crop((x0, y0, x0 + tw, y0 + th)).resize(
        (w, int(w / ratio)), Image.LANCZOS)

    a = np.asarray(im, dtype=np.float32) / 255.0

    # 1. desaturate toward luminance
    lum = (a * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(2, keepdims=True)
    a = lum + (a - lum) * 0.62

    # 2. split tone: blend darks to navy, brights to amber by luminance
    t = np.clip(lum, 0, 1)
    shadow_mix = (1 - t) ** 2.2 * 0.30
    high_mix = t ** 2.2 * 0.26
    a = a * (1 - shadow_mix) + (SHADOW / 255.0) * shadow_mix
    a = a * (1 - high_mix) + (HIGHLIGHT / 255.0) * high_mix

    # 3. vertical wash: amber sky over indigo ground, soft-light style
    h = a.shape[0]
    g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    wash = (SKY / 255.0) * (1 - g) + (GROUND / 255.0) * g
    a = a * (1 - 0.16) + (a * wash * 2.0) * 0.16

    # 4. contrast + slight lift so it sits at dusk, not noon
    a = np.clip((a - 0.5) * 1.16 + 0.5, 0, 1)
    a = a ** 1.06

    # 5. vignette
    yy = np.linspace(-1, 1, a.shape[0], dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, a.shape[1], dtype=np.float32)[None, :]
    r = np.sqrt(xx ** 2 + yy ** 2) / 1.414
    a *= (1 - 0.26 * np.clip(r, 0, 1) ** 2.1)[:, :, None]

    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), 'RGB')


def grade_file(src, dst, quality=76, **kw):
    grade(Image.open(src), **kw).save(
        dst, 'JPEG', quality=quality, optimize=True, progressive=True)
    import os
    return os.path.getsize(dst)
