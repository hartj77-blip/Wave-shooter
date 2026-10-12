"""Procedural PBR texture sets for Holdout. Everything tiles seamlessly (FFT noise and wrapped Voronoi).
Writes <name>_c.jpg (colour, sRGB), <name>_n.jpg (tangent-space normal) and <name>_r.jpg (R = ambient occlusion,
G = roughness, B = 0) into the output folder given on the command line."""
import sys, os
import numpy as np
from PIL import Image

OUT = sys.argv[1]
ONLY = set(sys.argv[2:])
os.makedirs(OUT, exist_ok=True)
R = np.random.default_rng


def fnoise(n, beta=2.0, seed=0, lo=1.0, hi=None):
    """Tileable fractal noise: white noise shaped by 1/f^beta in frequency space, normalised to 0..1."""
    rng = R(seed)
    w = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n) * n
    fx, fy = np.meshgrid(f, f)
    r = np.sqrt(fx ** 2 + fy ** 2)
    r[0, 0] = 1
    amp = 1 / r ** (beta / 2)
    amp[r < lo] = 0
    if hi:
        amp[r > hi] = 0
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * amp))
    out -= out.min()
    return out / max(out.max(), 1e-9)


def voronoi(n, pts, warp=None):
    """Wrapped Voronoi: distance to nearest and second-nearest point (pixels), and the nearest point's index."""
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    if warp is not None:
        xs = xs + warp[0]
        ys = ys + warp[1]
    f1 = np.full((n, n), 1e9, np.float32)
    f2 = np.full((n, n), 1e9, np.float32)
    idx = np.zeros((n, n), np.int32)
    for i, (px, py, sx, sy) in enumerate(pts):
        dx = (xs - px + n / 2) % n - n / 2
        dy = (ys - py + n / 2) % n - n / 2
        d = np.sqrt((dx * sx) ** 2 + (dy * sy) ** 2)
        closer = d < f1
        f2 = np.where(closer, f1, np.minimum(f2, d))
        idx = np.where(closer, i, idx)
        f1 = np.where(closer, d, f1)
    return f1, f2, idx


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def blur(img, rad):
    """Wrapped Gaussian blur through the FFT."""
    n = img.shape[0]
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f, f)
    g = np.exp(-(fx ** 2 + fy ** 2) * (2 * np.pi * rad) ** 2 / 2)
    if img.ndim == 3:
        return np.stack([np.real(np.fft.ifft2(np.fft.fft2(img[..., c]) * g)) for c in range(img.shape[2])], -1)
    return np.real(np.fft.ifft2(np.fft.fft2(img) * g))


def normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    nz = np.ones_like(h)
    l = np.sqrt(dx * dx + dy * dy + 1)
    # image rows run down while texture v runs up, hence +dy for the green channel
    return np.stack([-dx / l, dy / l, nz / l], -1) * .5 + .5


def ao_from_height(h, rad, k):
    return np.clip(1 - np.maximum(0, blur(h, rad) - h) * k, 0, 1)


def save(name, col=None, nrm=None, ao=None, rough=None, alpha=None, q=88):
    if ONLY and name not in ONLY:
        return
    if col is not None:
        c = np.clip(col, 0, 1) ** (1 / 2.2)  # linear-ish working space to sRGB
        img = Image.fromarray((c * 255 + .5).astype(np.uint8))
        if alpha is not None:
            img = Image.fromarray(np.dstack([(c * 255 + .5).astype(np.uint8), (np.clip(alpha, 0, 1) * 255 + .5).astype(np.uint8)]), 'RGBA')
            img.save(f'{OUT}/{name}_c.png', optimize=True)
        else:
            img.save(f'{OUT}/{name}_c.jpg', quality=q, optimize=True)
    if nrm is not None:
        Image.fromarray((np.clip(nrm, 0, 1) * 255 + .5).astype(np.uint8)).save(f'{OUT}/{name}_n.jpg', quality=q, optimize=True)
    if ao is not None or rough is not None:
        n = (ao if ao is not None else rough).shape[0]
        a = ao if ao is not None else np.ones((n, n))
        r = rough if rough is not None else np.ones((n, n))
        Image.fromarray((np.clip(np.stack([a, r, np.zeros_like(a)], -1), 0, 1) * 255 + .5).astype(np.uint8)).save(f'{OUT}/{name}_r.jpg', quality=q, optimize=True)
    print('wrote', name)


def lin(hexcol):
    h = hexcol.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]) ** 2.2


def per_cell(idx, rng, k):
    """A random value per Voronoi cell, broadcast over the image."""
    v = rng.random((k,) + idx.shape[2:] if False else k)
    return v[idx]


# ---------------------------------------------------------------- cobblestones (one tile = 3.2 m)
def cobble():
    n = 1024
    rng = R(3)
    rows, per = 13, 13
    pts = []
    for j in range(rows):
        for i in range(per):
            x = (i + (j % 2) * .5 + rng.uniform(-.28, .28)) * n / per
            y = (j + rng.uniform(-.18, .18)) * n / rows
            pts.append((x % n, y % n, rng.uniform(.85, 1.1), rng.uniform(1.0, 1.4)))
    wamp = n / per * .22
    warp = ((fnoise(n, 2.4, 14, lo=6) - .5) * 2 * wamp, (fnoise(n, 2.4, 15, lo=6) - .5) * 2 * wamp)
    f1, f2, idx = voronoi(n, pts, warp)
    edge = (f2 - f1)
    k = len(pts)
    stone = smooth(edge, 1.5, 14)
    dome = np.clip(1 - (f1 / (n / per * .62)) ** 2, 0, 1)
    rough_n = fnoise(n, 1.6, 4, lo=8)
    chip = fnoise(n, 2.2, 5, lo=20)
    h = stone * (.55 + .35 * dome + .12 * rough_n) - (1 - stone) * .05 + .04 * chip * stone
    # per-stone colour: weathered granite greys and warm sandstone
    tone = per_cell(idx, R(7), k)
    warm = per_cell(idx, R(8), k)
    base = np.where(warm[..., None] > .85, lin('#857a6a'), lin('#7a7a76') * (1 + .06 * (warm[..., None] - .5)))
    base = base * (.62 + .55 * tone[..., None])
    speck = fnoise(n, .3, 9, lo=200)
    base = base * (.85 + .3 * speck[..., None])
    dirt_l = fnoise(n, 2.0, 11, lo=2)
    grime = smooth(dirt_l, .45, .85)
    col = base * (1 - .35 * grime[..., None])
    gap = lin('#2e2820') * (.8 + .4 * fnoise(n, 1.5, 12)[..., None])
    moss = smooth(fnoise(n, 2.2, 13, lo=3), .62, .8) * (1 - stone)
    gap = gap * (1 - moss[..., None]) + lin('#3d4426') * moss[..., None]
    col = col * stone[..., None] + gap * (1 - stone[..., None])
    ao = ao_from_height(h, 4, 3.2) * (.55 + .45 * smooth(edge, 0, 10))
    col *= (.55 + .45 * ao)[..., None]
    rough = np.clip(.62 + .25 * (1 - stone) + .1 * speck - .12 * dome * stone, 0, 1)
    save('cobble', col, normal_from_height(h, 9), ao, rough)


# ---------------------------------------------------------------- lime plaster, greyscale so each house can tint it (tile = 4 m)
def plaster():
    n = 1024
    stucco = fnoise(n, 1.2, 21, lo=40)
    trowel = fnoise(n, 2.4, 22, lo=3)
    mid = fnoise(n, 2.0, 23, lo=10)
    h = .5 * trowel + .25 * mid + .12 * stucco
    # patches where the plaster has fallen off and brick shows
    pnoise = fnoise(n, 3.0, 24, lo=1)
    patch = smooth(pnoise, .8, .815) * 0
    rim = smooth(pnoise, .7, .85) * .6
    ys, xs = np.mgrid[0:n, 0:n]
    bh, bw = n / 48, n / 20
    row = (ys // bh).astype(int)
    bx = (xs + (row % 2) * bw / 2) % bw
    by = ys % bh
    mortar = 1 - smooth(np.minimum(np.minimum(bx, bw - bx), np.minimum(by, bh - by)), 0, 2.2)
    brick_id = (row * 97 + ((xs + (row % 2) * bw / 2) // bw).astype(int) * 31) % 1013
    brick_tone = R(25).random(1013)[brick_id]
    brick = lin('#86604c') * (.7 + .45 * brick_tone[..., None])
    brick = brick * (1 - mortar[..., None]) + lin('#b9ad98') * mortar[..., None]
    h = h * (1 - patch) + (patch * (.15 - .1 * mortar))
    base = np.ones((n, n, 3)) * (.74 + .14 * (mid[..., None] - .5)) + .05 * (stucco[..., None] - .5)
    base *= (1 - .25 * rim[..., None])
    stains = smooth(fnoise(n, 2.3, 26, lo=2), .55, .9)
    base *= (1 - .18 * stains[..., None])
    col = base * (1 - patch[..., None]) + brick * patch[..., None]
    # hairline cracks along Voronoi edges
    rng = R(27)
    pts = [(rng.uniform(0, n), rng.uniform(0, n), 1, 1) for _ in range(18)]
    f1, f2, _ = voronoi(n, pts)
    crackmask = smooth(fnoise(n, 2, 28, lo=2), .55, .7)
    crack = (1 - smooth(f2 - f1, 0, 1.6)) * crackmask
    col *= (1 - .45 * crack[..., None])
    h -= crack * .3
    ao = ao_from_height(h, 3, 2)
    rough = np.clip(.85 + .1 * stucco - .1 * patch, 0, 1)
    save('plaster', col, normal_from_height(h, 5), ao, rough)


# ---------------------------------------------------------------- dressed stone blocks (tile = 2.5 m)
def stone():
    n = 1024
    rng = R(31)
    rows = 6
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    bh = n / rows
    row = (ys // bh).astype(int)
    widths = []
    h = np.zeros((n, n))
    tone = np.zeros((n, n))
    for j in range(rows):
        x = rng.uniform(0, n / 3)
        cuts = []
        while x < n + x * 0:
            cuts.append(x)
            x += rng.uniform(n / 5, n / 2.6)
            if x > cuts[0] + n - n / 6:
                break
        cuts.append(cuts[0] + n)
        sel = row == j
        yy = ys - j * bh
        for a, b in zip(cuts[:-1], cuts[1:]):
            xx = (xs - a) % n
            inside = sel & (xx < (b - a))
            d = np.minimum(np.minimum(xx, (b - a) - xx), np.minimum(yy, bh - yy))
            h[inside] = smooth(d, 0, 9)[inside]
            tone[inside] = rng.random()
    chisel = fnoise(n, 1.4, 32, lo=30)
    big = fnoise(n, 2.2, 33, lo=2)
    h = h * (.8 + .2 * chisel) + .1 * big * h
    base = lin('#a59a87') * (.7 + .45 * tone[..., None]) * (.85 + .3 * chisel[..., None])
    stain = smooth(fnoise(n, 2.4, 34, lo=2), .5, .9)
    base *= (1 - .3 * stain[..., None])
    mortar = lin('#6d655a')
    m = smooth(h, 0, .4)
    col = base * m[..., None] + mortar * (1 - m[..., None])
    ao = ao_from_height(h, 3, 2.5)
    col *= (.6 + .4 * ao)[..., None]
    rough = np.clip(.8 + .15 * chisel, 0, 1)
    save('stone', col, normal_from_height(h, 7), ao, rough)


# ---------------------------------------------------------------- clay pantiles (tile = 2.2 m along the slope)
def roof():
    n = 1024
    cols_, rows = 10, 14
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    cw, rh = n / cols_, n / rows
    row = (ys // rh).astype(int)
    off = (row % 2) * cw * .5
    u = ((xs + off) % cw) / cw
    v = (ys % rh) / rh
    curve = np.sin(u * np.pi) ** .8  # rounded channel/cap profile
    lap = v  # each row overlaps the one below: thick at the bottom edge
    h = .55 * curve + .45 * lap - .5 * smooth(v, .9, 1.0)
    tile_id = row * cols_ + ((xs + off) // cw).astype(int)
    rnd = R(41).random(cols_ * rows + cols_)
    tone = rnd[tile_id % len(rnd)]
    base = lin('#a3502e') * (.62 + .5 * tone[..., None])
    base = base * (1 - (rnd[(tile_id * 7) % len(rnd)] > .9)[..., None] * .35)
    grain = fnoise(n, 1.3, 42, lo=40)
    base *= (.88 + .24 * grain[..., None])
    lichen = smooth(fnoise(n, 2.2, 43, lo=3), .6, .78) * smooth(fnoise(n, .5, 44, lo=100), .5, .7)
    base = base * (1 - lichen[..., None]) + lin('#a7a283') * lichen[..., None]
    soot = smooth(fnoise(n, 2.5, 45, lo=2), .5, .85)
    base *= (1 - .35 * soot[..., None])
    ao = ao_from_height(h, 4, 2.5) * (.6 + .4 * smooth(v, 0, .25))
    seam = smooth(np.minimum(u, 1 - u), 0, .06)
    shade = (.5 + .5 * curve) * (.35 + .65 * seam) * (.7 + .3 * smooth(v, 0, .5))
    col = base * (.45 + .55 * ao)[..., None] * shade[..., None]
    h = h - .4 * (1 - seam)
    rough = np.clip(.7 + .2 * grain + .1 * lichen, 0, 1)
    save('roof', col, normal_from_height(h, 6), ao, rough)


# ---------------------------------------------------------------- weathered planks (tile = 1.2 m)
def wood():
    n = 512
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    plank = (ys // (n / 4)).astype(int)
    grain = fnoise(n, 1.0, 51, lo=1, hi=None)
    streak = np.stack([fnoise(n, 2.5, 52 + i, lo=1) for i in range(1)], 0)[0]
    g = np.sin((ys / n * 4 * 9 + streak * 18 + plank * 3.1) * np.pi * 2) * .5 + .5
    gap = 1 - smooth(np.minimum(ys % (n / 4), n / 4 - ys % (n / 4)), 0, 2.5)
    tone = R(53).random(8)[plank % 8]
    base = lin('#8a6440') * (.65 + .45 * tone[..., None]) * (.8 + .25 * g[..., None]) * (.9 + .2 * grain[..., None])
    weather = smooth(fnoise(n, 2.2, 54, lo=2), .45, .8)
    base = base * (1 - weather[..., None] * .5) + lin('#7d7568') * weather[..., None] * .5
    col = base * (1 - .7 * gap[..., None])
    h = .5 + .2 * g + .1 * grain - .6 * gap
    save('wood', col, normal_from_height(h, 4), ao_from_height(h, 2, 2), np.clip(.7 + .2 * weather, 0, 1))


# ---------------------------------------------------------------- concrete (tile = 2 m)
def concrete():
    n = 512
    a = fnoise(n, 1.0, 61, lo=60)
    b = fnoise(n, 2.2, 62, lo=2)
    pits = smooth(fnoise(n, .2, 63, lo=150), .8, .9)
    h = .4 * b + .2 * a - .3 * pits
    col = np.ones((n, n, 3)) * lin('#a8a397') * (.8 + .3 * b[..., None]) * (.9 + .15 * a[..., None])
    col *= (1 - .4 * pits[..., None])
    stain = smooth(fnoise(n, 2.5, 64, lo=2), .55, .85)
    col *= (1 - .25 * stain[..., None])
    save('concrete', col, normal_from_height(h, 3), ao_from_height(h, 2, 2), np.clip(.85 + .1 * a, 0, 1))


# ---------------------------------------------------------------- painted metal with chips and rust, greyscale paint (tile = 1 m)
def metal():
    n = 512
    chips = smooth(fnoise(n, 2.0, 71, lo=4) * .6 + fnoise(n, .8, 72, lo=40) * .4, .66, .7)
    rust = smooth(fnoise(n, 2.2, 73, lo=3), .6, .8)
    scratch = fnoise(n, 1.0, 74, lo=60)
    paint = np.ones((n, n, 3)) * (.85 + .15 * scratch[..., None])
    bare = lin('#6b625a') * (.8 + .3 * scratch[..., None])
    rustc = lin('#6e3a1e') * (.7 + .5 * fnoise(n, .8, 75, lo=30)[..., None])
    col = paint * (1 - chips[..., None]) + bare * chips[..., None]
    col = col * (1 - rust[..., None] * .7) + rustc * rust[..., None] * .7
    h = .5 - .25 * chips + .15 * rust * fnoise(n, .5, 76, lo=60)
    rough = np.clip(.45 + .3 * chips + .35 * rust + .05 * scratch, 0, 1)
    save('metal', col, normal_from_height(h, 3), ao_from_height(h, 2, 2), rough)


# ---------------------------------------------------------------- uniform fabric: camouflage blotches over a twill weave (tile = .8 m)
def camo():
    n = 512
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    weave = (np.sin((xs + ys) * np.pi * 2 / 4) * .5 + .5) * .6 + (np.sin((xs - ys) * np.pi * 2 / 9) * .5 + .5) * .4
    l1 = fnoise(n, 2.6, 81, lo=2)
    l2 = fnoise(n, 2.6, 82, lo=3)
    l3 = fnoise(n, 2.4, 83, lo=4)
    cA, cB, cC, cD = lin('#7d7a5c'), lin('#5b5a40'), lin('#9d9474'), lin('#3d3a2c')
    col = np.ones((n, n, 3)) * cA
    col = np.where((l1 > .58)[..., None], cB, col)
    col = np.where((l2 > .64)[..., None], cC, col)
    col = np.where((l3 > .7)[..., None], cD, col)
    col = blur(col, .8)
    col *= (.85 + .25 * weave[..., None])
    grime = fnoise(n, 2.0, 84, lo=2)
    col *= (.85 + .25 * grime[..., None])
    h = .5 + .25 * weave + .1 * fnoise(n, 1.4, 85, lo=20)
    # greyscale version for tinted uniforms (elite, juggernaut)
    save('camo', col, normal_from_height(h, 2.5), ao_from_height(h, 1.5, 1.5), np.clip(.9 + 0 * h, 0, 1))
    g = col.mean(-1, keepdims=True) / col.mean()
    save('fabric', np.repeat(np.clip(g * .75, 0, 1), 3, -1) ** 1.0)


# ---------------------------------------------------------------- bark (tile = 1 m around, 2 m up)
def bark():
    n = 512
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    f = fnoise(n, 2.0, 91, lo=2)
    ridges = np.abs(np.sin((xs / n * 9 + f * 2.5) * np.pi))
    h = ridges ** .6 * .7 + .3 * fnoise(n, 1.4, 92, lo=20)
    col = lin('#5b4a3a') * (.5 + .6 * h[..., None])
    moss = smooth(fnoise(n, 2.2, 93, lo=2), .6, .8)
    col = col * (1 - moss[..., None] * .6) + lin('#59613a') * moss[..., None] * .6
    save('bark', col, normal_from_height(h, 6), ao_from_height(h, 3, 2), np.clip(.9 + 0 * h, 0, 1))


# ---------------------------------------------------------------- leaf clusters with alpha, four variants in a 2x2 atlas
def leaves():
    n = 1024
    rng = R(101)
    col = np.zeros((n, n, 3))
    alpha = np.zeros((n, n))
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    half = n // 2
    for q in range(4):
        ox, oy = (q % 2) * half, (q // 2) * half
        cx, cy = ox + half / 2, oy + half / 2
        for _ in range(170):
            r = np.sqrt(rng.random()) * half * .42
            a = rng.uniform(0, 2 * np.pi)
            x, y = cx + np.cos(a) * r, cy + np.sin(a) * r
            L, W = rng.uniform(26, 44), rng.uniform(10, 16)
            ang = rng.uniform(0, np.pi)
            x0, x1 = int(max(ox, x - L)), int(min(ox + half, x + L))
            y0, y1 = int(max(oy, y - L)), int(min(oy + half, y + L))
            if x1 <= x0 or y1 <= y0:
                continue
            sx, sy = xs[y0:y1, x0:x1] - x, ys[y0:y1, x0:x1] - y
            u = sx * np.cos(ang) + sy * np.sin(ang)
            v = -sx * np.sin(ang) + sy * np.cos(ang)
            t = u / L
            shape = (v / (W * np.clip(1 - t * t, 0, 1) ** .7 + 1e-3)) ** 2 + t * t
            m = shape < 1
            shade = rng.uniform(.55, 1.15)
            hue = rng.random()
            c = (lin('#4f6b2c') * (1 - hue) + lin('#7a8f3c') * hue) * shade
            vein = np.exp(-(v / 1.2) ** 2) * (np.abs(t) < .9)
            lit = np.clip(.75 + .35 * (1 - np.abs(v) / W) - .25 * vein, .4, 1.2)
            sub = col[y0:y1, x0:x1]
            sub[m] = (c[None, :] * lit[m][:, None])
            alpha[y0:y1, x0:x1][m] = 1
    # darken towards the cluster centre for self-shadowing
    for q in range(4):
        ox, oy = (q % 2) * half, (q // 2) * half
        d = np.sqrt((xs[oy:oy + half, ox:ox + half] - ox - half / 2) ** 2 + (ys[oy:oy + half, ox:ox + half] - oy - half / 2) ** 2) / (half * .45)
        col[oy:oy + half, ox:ox + half] *= (.55 + .45 * np.clip(d, 0, 1))[..., None]
    save('leaves', col, alpha=alpha)


# ---------------------------------------------------------------- large-scale variation for the ground, to hide tiling (covers 96 m)
def macro():
    n = 512
    a = fnoise(n, 2.4, 111, lo=1)
    b = fnoise(n, 1.8, 112, lo=4)
    wet = smooth(fnoise(n, 2.6, 113, lo=2), .7, .76)
    img = np.stack([.75 + .5 * a, .75 + .5 * b, wet], -1)
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(f'{OUT}/macro.jpg', quality=90)
    print('wrote macro')


for fn in [cobble, plaster, stone, roof, wood, concrete, metal, camo, bark, leaves, macro]:
    if not ONLY or fn.__name__ in ONLY or (fn.__name__ == 'camo' and 'fabric' in ONLY):
        fn()


# ---------------------------------------------------------------- burlap for sandbags (tile = .5 m)
def burlap():
    n = 256
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    wx = np.sin(xs * np.pi * 2 / 6 + fnoise(n, 1.5, 121, lo=8) * 2) * .5 + .5
    wy = np.sin(ys * np.pi * 2 / 6 + fnoise(n, 1.5, 122, lo=8) * 2) * .5 + .5
    weave = np.where(((xs // 6 + ys // 6) % 2) == 0, wx, wy)
    dirt = fnoise(n, 2.2, 123, lo=2)
    col = lin('#b59e74') * (.75 + .3 * weave[..., None]) * (.8 + .3 * dirt[..., None])
    h = .5 + .4 * weave
    save('burlap', col, normal_from_height(h, 2.5))


if 'burlap' in ONLY:
    burlap()
