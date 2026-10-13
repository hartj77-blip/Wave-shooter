#!/usr/bin/env python3
"""Build tex/v6/sky.jpg from a CC0 Poly Haven HDRI (see CREDITS.md).

Usage: python3 tools/realsky.py tex/v6 [cache_dir]

Decodes the Radiance .hdr, turns it so its sun sits where the game's sun light is (SUN in index.html), keeps the
upper hemisphere and stores it in 8 bits with a reversible curve, v = L/(L+K), so the game can recover the HDR
radiance (L = K v/(1-v)) for the background and the environment lighting. Needs Python 3 with NumPy and Pillow.
"""
import math, os, sys, urllib.request
import numpy as np
from PIL import Image

HDRI = 'kloofendal_38d_partly_cloudy_puresky'   # sun about 38 degrees up, like the game's
RES = '4k'
SUN = (-.55, .62, .42)                          # the game's sun direction
K = .5                                          # curve knee; keep in step with SKY_K in index.html
LEVEL = .42                                     # mean sky radiance between 15 and 60 degrees up, in game units
W, H = 4096, 1152                               # 0 to 90 degrees up, plus 11.25 below the horizon

opener = urllib.request.build_opener(); opener.addheaders = [('User-Agent', 'holdout-sky-build/1.0')]


def read_hdr(path):
    """Radiance RGBE with new-style run-length encoding, as Poly Haven ships it."""
    with open(path, 'rb') as f:
        data = f.read()
    pos = 0
    while True:
        end = data.index(b'\n', pos); line = data[pos:end]; pos = end + 1
        if line.startswith(b'-Y'):
            _, h, _, w = line.split(); h, w = int(h), int(w); break
    img = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        if data[pos] != 2 or data[pos + 1] != 2:
            raise ValueError('only RLE scanlines are supported')
        pos += 4
        for c in range(4):
            x = 0; row = img[y, :, c]
            while x < w:
                n = data[pos]; pos += 1
                if n > 128:
                    n -= 128; row[x:x + n] = data[pos]; pos += 1
                else:
                    row[x:x + n] = np.frombuffer(data, np.uint8, n, pos); pos += n
                x += n
    e = img[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0)
    return img[..., :3].astype(np.float32) * scale[..., None].astype(np.float32)


def main():
    dst = sys.argv[1] if len(sys.argv) > 1 else 'tex/v6'
    cache = sys.argv[2] if len(sys.argv) > 2 else '.skycache'
    os.makedirs(dst, exist_ok=True); os.makedirs(cache, exist_ok=True)
    url = f'https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/{RES}/{HDRI}_{RES}.hdr'
    p = os.path.join(cache, url.split('/')[-1])
    if not os.path.exists(p):
        with opener.open(url) as r, open(p, 'wb') as f:
            f.write(r.read())
    hdr = read_hdr(p)
    h, w, _ = hdr.shape
    # the game samples u = atan(d.z, d.x)/2pi + .5, v = asin(d.y)/pi + .5 (row 0 = straight up); roll the sun into place
    lum = hdr @ np.array([.2126, .7152, .0722], np.float32)
    sy, sx = np.unravel_index(np.argmax(lum[: h // 2]), lum[: h // 2].shape)
    s = np.array(SUN) / np.linalg.norm(SUN)
    want = (math.atan2(s[2], s[0]) / (2 * math.pi) + .5) * w
    hdr = np.roll(hdr, int(round(want - sx)), axis=1)
    print('HDRI sun elevation %.1f deg, game sun %.1f deg' % (90 - (sy + .5) / h * 180, math.degrees(math.asin(s[1]))))
    # level it to the game's lighting, measured on the sky away from the sun
    rows = slice(int(h * (90 - 60) / 180), int(h * (90 - 15) / 180))
    band = lum[rows]; band = band[band < np.percentile(band, 98)]
    hdr *= LEVEL / band.mean()
    sky = hdr[: int(h * (90 + 11.25) / 180)]
    sky = np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(sky[..., c])).resize((W, H), Image.BILINEAR)) for c in range(3)], 2)
    hz = sky[int(H * 90 / 101.25) - 40: int(H * 90 / 101.25) - 4].reshape(-1, 3).mean(0)
    print('horizon colour (linear):', hz.round(3), 'sRGB hex: #%02x%02x%02x' % tuple(int(255 * (c ** (1 / 2.2)) + .5) for c in np.clip(hz, 0, 1)))
    v = sky / (sky + K)
    Image.fromarray((np.clip(v, 0, 1) * 255 + .5).astype(np.uint8)).save(os.path.join(dst, 'sky.jpg'), quality=90, optimize=True)
    print(os.path.join(dst, 'sky.jpg'), os.path.getsize(os.path.join(dst, 'sky.jpg')))


if __name__ == '__main__':
    main()
