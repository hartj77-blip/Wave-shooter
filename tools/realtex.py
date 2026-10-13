#!/usr/bin/env python3
"""Build tex/v6/: photo-scanned CC0 surface textures from Poly Haven and ambientCG (see CREDITS.md).

Usage: python3 tools/realtex.py tex/v6 [cache_dir]

Downloads the 1K maps (cached in cache_dir, default ./.texcache) and packs them into the game's convention:
<name>_c.jpg colour, <name>_n.jpg OpenGL normal map, <name>_r.jpg ambient occlusion in red and roughness in green.
Needs Python 3 with NumPy and Pillow. The older generated set in tex/ is left alone, because old versions use it.
"""
import io, json, os, sys, urllib.request, zipfile
import numpy as np
from PIL import Image

UA = [('User-Agent', 'holdout-texture-build/1.0')]
opener = urllib.request.build_opener(); opener.addheaders = UA

# name in the game -> Poly Haven asset. The game sets each material's repeat to match the scan's real size.
POLYHAVEN = {
    'cobble': 'cobblestone_01',          # 2.4 m
    'plaster': 'painted_plaster_wall',   # 2 m, made greyscale so each house can tint it
    'stone': 'sandstone_blocks_05',      # 3 m
    'roof': 'clay_roof_tiles_02',        # 2.5 m
    'wood': 'weathered_planks',          # 2 m
    'concrete': 'concrete_wall_006',     # 2 m
    'metal': 'rusty_metal_02',           # 1 m
    'bark': 'bark_brown_02',             # 1 m
    'burlap': 'hessian_380',             # .27 m
    'linen': 'rough_linen',              # .27 m: fabric, and the weave under the camouflage print
}
LEAVES = 'LeafSet024'                    # ambientCG


def get(url, cache):
    p = os.path.join(cache, url.split('/')[-1].split('=')[-1])
    if not os.path.exists(p):
        with opener.open(url) as r, open(p, 'wb') as f:
            f.write(r.read())
    return p


def ph_maps(aid, cache):
    with opener.open('https://api.polyhaven.com/files/' + aid) as r:
        files = json.load(r)
    out = {}
    for key, short in (('Diffuse', 'diff'), ('nor_gl', 'nor'), ('arm', 'arm')):
        out[short] = Image.open(get(files[key]['1k']['jpg']['url'], cache)).convert('RGB').resize((1024, 1024), Image.LANCZOS)
    return out


def arr(im):
    return np.asarray(im, dtype=np.float32) / 255


def img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8))


def save(dst, name, col=None, nrm=None, arm=None, size=1024):
    if col is not None:
        col.resize((size, size), Image.LANCZOS).save(os.path.join(dst, name + '_c.jpg'), quality=85, optimize=True)
    if nrm is not None:
        nrm.resize((size, size), Image.LANCZOS).save(os.path.join(dst, name + '_n.jpg'), quality=88, optimize=True)
    if arm is not None:
        a = arr(arm.resize((size, size), Image.LANCZOS))
        a[..., 2] = 0  # red: AO, green: roughness; blue (metalness in the source) is unused
        img(a).save(os.path.join(dst, name + '_r.jpg'), quality=85, optimize=True)


def grey(im, mean):
    """Greyscale, rescaled to a target mean, for materials the game tints."""
    g = arr(im.convert('L'))
    g = g * (mean / g.mean())
    return img(np.repeat(g[..., None], 3, 2))


def tile(im, n, size=1024):
    """Repeat an image n x n times inside one texture."""
    s = size // n
    t = im.resize((s, s), Image.LANCZOS)
    out = Image.new(im.mode, (s * n, s * n))
    for y in range(n):
        for x in range(n):
            out.paste(t, (x * s, y * s))
    return out.resize((size, size), Image.LANCZOS)


def leaves(dst, cache):
    """Four leaf clusters in a 2x2 atlas with alpha, made from photographed leaves."""
    z = zipfile.ZipFile(get(f'https://ambientcg.com/get?file={LEAVES}_1K-PNG.zip', cache))
    col = Image.open(io.BytesIO(z.read(f'{LEAVES}_1K-PNG_Color.png'))).convert('RGB')
    op = Image.open(io.BytesIO(z.read(f'{LEAVES}_1K-PNG_Opacity.png'))).convert('L')
    src = Image.merge('RGBA', (*col.split(), op))
    a = np.asarray(op) > 128
    def runs(v):
        r, s = [], None
        for i, x in enumerate(v):
            if x and s is None: s = i
            if not x and s is not None: r.append((s, i)); s = None
        if s is not None: r.append((s, len(v)))
        return r
    cuts = []
    for y0, y1 in runs(a.any(1)):
        for x0, x1 in runs(a[y0:y1].any(0)):
            if (x1 - x0) * (y1 - y0) > 4000:
                cuts.append(src.crop((x0, y0, x1, y1)))
    rng = np.random.default_rng(101)
    n, half = 1024, 512
    atlas = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    for q in range(4):
        ox, oy = (q % 2) * half, (q // 2) * half
        cl = Image.new('RGBA', (half, half), (0, 0, 0, 0))
        for _ in range(110):
            r = np.sqrt(rng.random()) * half * .36
            ang = rng.uniform(0, 2 * np.pi)
            x, y = half / 2 + np.cos(ang) * r, half / 2 + np.sin(ang) * r
            lf = cuts[rng.integers(len(cuts))]
            L = rng.uniform(62, 96)
            lf = lf.resize((max(4, int(lf.width * L / lf.height)), int(L)), Image.LANCZOS)
            # leaves near the centre sit deeper in the crown, so darker; a little colour variation between leaves
            shade = rng.uniform(.6, 1.05) * (.62 + .38 * min(1, r / (half * .36)))
            la = arr(lf)
            la[..., :3] *= shade * np.array([rng.uniform(.92, 1.02), 1, rng.uniform(.85, 1)], np.float32)
            lf = img(la).rotate(rng.uniform(0, 360), Image.BICUBIC, expand=True)
            cl.alpha_composite(lf, (int(x - lf.width / 2), int(y - lf.height / 2)))
        atlas.alpha_composite(cl, (ox, oy))
    c = arr(atlas)
    c[..., 3] = (c[..., 3] > .5).astype(np.float32)  # the game alpha-tests at .45
    img(c).save(os.path.join(dst, 'leaves_c.png'), optimize=True)


def main():
    dst = sys.argv[1] if len(sys.argv) > 1 else 'tex/v6'
    cache = sys.argv[2] if len(sys.argv) > 2 else '.texcache'
    os.makedirs(dst, exist_ok=True); os.makedirs(cache, exist_ok=True)
    m = {k: ph_maps(v, cache) for k, v in POLYHAVEN.items()}
    for k in ('cobble', 'stone', 'roof', 'wood', 'concrete', 'bark'):
        save(dst, k, m[k]['diff'], m[k]['nor'], m[k]['arm'])
    save(dst, 'plaster', grey(m['plaster']['diff'], .86), m['plaster']['nor'], m['plaster']['arm'])
    # painted steel with rust: brightened so the game's paint tint reads as before, rust keeps its hue
    mc = arr(m['metal']['diff']); save(dst, 'metal', img(mc * (.75 / mc.mean())), m['metal']['nor'], m['metal']['arm'], 512)
    save(dst, 'burlap', m['burlap']['diff'], m['burlap']['nor'], size=512)
    save(dst, 'fabric', grey(m['linen']['diff'], .86), size=512)
    # camouflage: the existing printed pattern (one tile = .8 m) on the scanned linen weave, three repeats per tile
    camo = arr(Image.open(os.path.join(os.path.dirname(dst.rstrip('/')), 'camo_c.jpg')).convert('RGB').resize((1024, 1024), Image.LANCZOS))
    weave = arr(tile(m['linen']['diff'], 3).convert('L'))
    camo *= (weave / weave.mean())[..., None] ** .7
    n = arr(tile(m['linen']['nor'], 3)) * 2 - 1
    n[..., :2] *= 3  # the weave is fine; strengthen it so it still reads at this scale
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    save(dst, 'camo', img(camo), img(n * .5 + .5), tile(m['linen']['arm'], 3), 512)
    leaves(dst, cache)


if __name__ == '__main__':
    main()
