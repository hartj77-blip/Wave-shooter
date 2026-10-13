#!/usr/bin/env python3
"""Build models/props/*.glb from CC0 Poly Haven models (see CREDITS.md).

Usage: python3 tools/realmodels.py models/props [cache_dir]

Downloads each model's 1K glTF, shrinks its textures and packs everything into one binary .glb, so the
game loads one small file per prop. Needs Python 3 with Pillow.
"""
import io, json, os, struct, sys, urllib.request
from PIL import Image

opener = urllib.request.build_opener(); opener.addheaders = [('User-Agent', 'holdout-model-build/1.0')]

# Poly Haven asset -> texture size in the .glb
MODELS = {
    'Barrel_01': 512,          # red oil drum
    'barrel_03': 512,          # blue oil drum
    'wooden_crate_02': 512,    # closed wooden crate
    'metal_jerrycan_green': 512,
    'ammo_box': 256,
    'old_tyre': 512,
    'service_pistol': 1024,    # first-person pistol: seen up close, so it keeps 1K textures
}


def fetch(url, cache):
    p = os.path.join(cache, url.split('/')[-1])
    if not os.path.exists(p):
        with opener.open(url) as r, open(p, 'wb') as f:
            f.write(r.read())
    with open(p, 'rb') as f:
        return f.read()


def pack(aid, size, cache, dst):
    with opener.open('https://api.polyhaven.com/files/' + aid) as r:
        info = json.load(r)['gltf']['1k']['gltf']
    gltf = json.loads(fetch(info['url'], cache))
    inc = {k: fetch(v['url'], cache) for k, v in info['include'].items()}
    blob = bytearray()

    def add(data):
        while len(blob) % 4: blob.append(0)
        off = len(blob); blob.extend(data); return off, len(data)

    # geometry: the original buffers, appended in order, with their bufferViews shifted to match
    shift = []
    for b in gltf['buffers']:
        off, _ = add(inc[b['uri']]); shift.append(off)
    for bv in gltf['bufferViews']:
        bv['byteOffset'] = bv.get('byteOffset', 0) + shift[bv['buffer']]; bv['buffer'] = 0
    # textures: resized, re-encoded and stored as bufferViews
    for im in gltf.get('images', []):
        src = Image.open(io.BytesIO(inc[im.pop('uri')]))
        if max(src.size) > size:
            src = src.resize((size, size * src.height // src.width), Image.LANCZOS)
        out = io.BytesIO(); src.convert('RGB').save(out, 'JPEG', quality=85, optimize=True)
        off, n = add(out.getvalue())
        gltf['bufferViews'].append({'buffer': 0, 'byteOffset': off, 'byteLength': n})
        im['bufferView'] = len(gltf['bufferViews']) - 1; im['mimeType'] = 'image/jpeg'
    while len(blob) % 4: blob.append(0)
    gltf['buffers'] = [{'byteLength': len(blob)}]
    js = json.dumps(gltf, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    glb = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob))
    glb += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(blob), 0x004E4942) + bytes(blob)
    p = os.path.join(dst, aid.lower() + '.glb')
    with open(p, 'wb') as f:
        f.write(glb)
    print(p, len(glb))


def main():
    dst = sys.argv[1] if len(sys.argv) > 1 else 'models/props'
    cache = sys.argv[2] if len(sys.argv) > 2 else '.modelcache'
    os.makedirs(dst, exist_ok=True); os.makedirs(cache, exist_ok=True)
    for aid, size in MODELS.items():
        pack(aid, size, cache, dst)


if __name__ == '__main__':
    main()
