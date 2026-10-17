# Wave Shooter

**Holdout** is a browser wave-survival shooter in the style of Modern Warfare 3's Survival mode. Hold a village square against waves of soldiers, attack dogs, juggernauts and helicopters. Earn cash for kills and survived waves, then spend it at three armories:

- **Weapons:** pistols, SMG, assault rifles, shotgun, sniper rifle, LMG and an RPG, plus red dot sights, foregrips and extended mags.
- **Equipment:** frag grenades, smoke grenades, flashbangs, firebombs, body armor, a helmet, a self-revive kit and a sentry gun.
- **Air support:** a precision airstrike, a two-man Delta squad and an attack helicopter.

Number keys buy at an armory, "Buy again" repeats your last order there, and "Refill all ammo" restocks every gun at once.

Pick the weather and time of day on the title screen: clear day, dusk, night (your gun gets a flashlight), rain, thick fog, or a mix that changes every three waves. Enemies see less far in the dark, rain and fog. Settings (title screen or pause menu) cover mouse and touch sensitivity, field of view, game and voice volume, graphics quality and an FPS counter, and are saved in the browser.

Play solo, or host a co-op room for up to four players with voice chat. Co-op runs peer to peer over WebRTC (PeerJS), so there's no server to run: friends open the page, type the 4-letter room code and join.

## Play

Open `index.html` in a browser, or host the repo on GitHub Pages (Settings → Pages → Deploy from a branch → `main` / root).

Controls: WASD to move, Shift to sprint, C to crouch, mouse to aim and shoot, R to reload, G for a frag grenade, X for a smoke, flashbang or firebomb, V to knife, F to use an armory or hold to revive a squadmate, 4 to deploy an airstrike or sentry, N to start the next wave early, M for voice chat. Phones and tablets get on-screen controls.

 https://hartj77-blip.github.io/Wave-shooter/

## How it's built

The game is in `index.html`: three.js r128 (`lib/three.min.js`, MIT) for rendering, no build step. Third-party assets and their licences are listed in `CREDITS.md`. Every real asset has a fallback, so the game still runs if a file fails to load.

- **Surfaces:** photo-scanned CC0 textures from Poly Haven and ambientCG in `tex/v6/`. Each set is a colour map `_c`, a normal map `_n` and `_r` with ambient occlusion in red and roughness in green. `python3 tools/realtex.py tex/v6` downloads and rebuilds them (Python 3 with NumPy and Pillow). Older versions use the generated set in `tex/`, made by `tools/tex.py`.
- **Sky and lighting:** a CC0 Poly Haven HDRI, turned so its sun lines up with the game's sun light, and stored as `tex/v6/sky.jpg` with a reversible curve that keeps its brightness range. It is both the background and the environment lighting. `python3 tools/realsky.py tex/v6` rebuilds it. Until it loads, a procedural sky stands in.
- **Props and the pistol:** CC0 Poly Haven models in `models/props/`, packed into small `.glb` files by `python3 tools/realmodels.py models/props`. Crates and barrels keep simple invisible shapes for bullets and collisions, which also show if a model fails to load.
- **Soldiers:** an animated glTF model in `models/`, loaded with the three.js loaders in `lib/`. If it fails to load, the game falls back to its built-in soldiers.
- **Sound:** gunfire, explosions and bullet impacts are CC0 recordings from Freesound in `sounds/`, cut into single shots by `python3 tools/realsound.py sounds` (needs ffmpeg). The game adds street echo and a speed-of-sound delay for distant shots. Everything else is synthesized, and so is any recording that hasn't loaded.
- **Co-op:** `peerjs.min.js` is a local copy of PeerJS 1.5 (the page falls back to jsDelivr if it's missing).

To play-test automatically, run `node tests/playtest.js` (needs Playwright: `npm i -g playwright && npx playwright install chromium`). It plays a solo game through 12 waves with an invulnerable player, checks that every wave ends and no enemy gets stuck out of reach, then checks that dying and restarting gives a clean run. Set `WAVES=20` for a longer run.

For local co-op testing, run a PeerJS server and open `http://localhost:8000/?peerServer=localhost:9000`.

### Co-op relay

Players normally connect directly. Some networks, mobile data especially, block that, and joining fails with "Couldn't connect to that room". A relay (TURN) server fixes it. By default the game uses free public relays (PeerJS's and Metered's open relay), which need no account but can be busy. For a dependable one, sign up for the free plan at [metered.ca](https://www.metered.ca/), then put your app name and API key into `RELAY` near the top of the networking code in `index.html`. The key is meant to be used from browsers, and Metered caps usage on the free plan.

## Versions

Every release stays playable. `index.html` is the latest build, `versions.html` lists the older ones, and each old build is a frozen copy in `versions/`. Before changing `index.html` for a new release, copy it to `versions/<n>-<name>.html`, add a card for it in `versions.html`, and bump `NET_PREFIX` in the new build so old and new co-op rooms don't mix. From version 4 on, a frozen copy loads its textures from `tex/` one folder up, so change `'tex/'` to `'../tex/'` in the copy, and keep any texture an old version uses. From version 5 on, do the same for `lib/` (the script tags) and `models/` (the soldier loader). From version 6 on, also do it for the sky (`'tex/v6/sky.jpg'`), the props (`'models/props/'`) and `sounds/`. Put replacement assets under new names or folders (like `tex/v6/`) rather than overwriting files an old version uses.
