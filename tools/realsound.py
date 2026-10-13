#!/usr/bin/env python3
"""Build sounds/*.mp3: single gunshots, blasts and impacts cut from CC0 recordings on Freesound (see CREDITS.md).

Usage: python3 tools/realsound.py sounds [cache_dir]

Each clip names a Freesound preview, a rough start time and a length. The script finds the exact onset near that
time, cuts the clip, fades it out, normalises it and encodes a small mono MP3. The game adds its own street reverb and
speed-of-sound delay, so the clips are kept short. Needs Python 3 with NumPy, and ffmpeg.
"""
import os, subprocess, sys, urllib.request
import numpy as np

SR = 44100
PREVIEW = 'https://cdn.freesound.org/previews/{}/{}-hq.mp3'
opener = urllib.request.build_opener(); opener.addheaders = [('User-Agent', 'Mozilla/5.0 holdout-sound-build')]

# name: (preview id, start s, length s, peak dBFS). Recordings:
#  828786 Glock 19X, outdoors (areniporgen)          702672 Remington 870, outdoors (areniporgen)
#  205588 US military training range gunfire (qubodup, public domain)   184750 AK-47s on a training range (qubodup)
#  855595 Barrett M82A1 at a sniper championship (qubodup)
#  184274 anti-tank weapons fired on a range (qubodup)     855247 military training explosion (qubodup)
#  182263 bullet hitting metal, foley (martian)   560966 stone strikes (Bricklover)   537755 wooden planks dropped (Tim_Verberne)
#  319222 rock hitting dirt (worthahep88)
CLIPS = {
    'pistol':    ('828786_15072041', 0.0, .9, -1),
    'shotgun':   ('702672_15072041', 0.0, .9, -1),
    'rifle':     ('205588_71257', 18.69, .8, -1),
    'ak':        ('184750_71257', 19.07, .75, -1),
    'sniper':    ('855595_71257', 0.0, 1.5, -1),
    'launcher':  ('184274_71257', 20.0, 2.2, -1),
    'blast':     ('855247_71257', 0.0, 1.9, -1),
    'hit_metal1': ('182263_84709', 2.44, .4, -3),
    'hit_metal2': ('182263_84709', 10.57, .4, -3),
    'hit_stone1': ('560966_8919922', .3, .3, -3),
    'hit_stone2': ('560966_8919922', 4.38, .3, -3),
    'hit_wood1':  ('537755_4838691', 6.36, .3, -3),
    'hit_wood2':  ('537755_4838691', 9.01, .3, -3),
    'hit_dirt':   ('319222_3443504', .27, .4, -3),
}


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def main():
    dst = sys.argv[1] if len(sys.argv) > 1 else 'sounds'
    cache = sys.argv[2] if len(sys.argv) > 2 else '.soundcache'
    os.makedirs(dst, exist_ok=True); os.makedirs(cache, exist_ok=True)
    for name, (pid, start, dur, peak) in CLIPS.items():
        p = os.path.join(cache, pid + '-hq.mp3')
        if not os.path.exists(p):
            with opener.open(PREVIEW.format(pid[:3], pid)) as r, open(p, 'wb') as f:
                f.write(r.read())
        x = decode(p)
        # the onset: the loudest transient within 300 ms of the given start, backed up to where it first
        # reaches a fifth of its peak (searching 30 ms before it)
        a = int(start * SR); w = np.abs(x[a:a + int(.3 * SR)]); pk = a + int(np.argmax(w))
        b0 = max(0, pk - int(.03 * SR)); seg = np.abs(x[b0:pk + 1])
        i = b0 + int(np.argmax(seg >= seg.max() * .2))
        i = max(0, i - int(.003 * SR))
        y = x[i:i + int(dur * SR)].astype(np.float64)
        y -= y.mean()
        n = len(y); fade = np.ones(n)
        fade[:int(.002 * SR)] = np.linspace(0, 1, int(.002 * SR))
        k = int(n * .35); fade[n - k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
        y *= fade
        y *= 10 ** (peak / 20) / np.abs(y).max()
        out = os.path.join(dst, name + '.mp3')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f64le', '-ar', str(SR), '-ac', '1', '-i', '-',
                        '-af', 'highpass=f=30', '-c:a', 'libmp3lame', '-b:a', '96k', out],
                       input=y.astype('<f8').tobytes(), check=True)
        print(out, os.path.getsize(out))


if __name__ == '__main__':
    main()
