# Wave Shooter

**Holdout** is a browser wave-survival shooter in the style of Modern Warfare 3's Survival mode. Hold a village square against waves of soldiers, attack dogs, juggernauts and helicopters. Earn cash for kills and survived waves, then spend it at three armories:

- **Weapons:** pistols, SMG, assault rifles, shotgun, sniper rifle, LMG and an RPG, plus red dot sights, foregrips and extended mags.
- **Equipment:** frag grenades, body armor, a self-revive kit and a sentry gun.
- **Air support:** a precision airstrike, a two-man Delta squad and an attack helicopter.

Play solo, or host a co-op room for up to four players with voice chat. Co-op runs peer to peer over WebRTC (PeerJS), so there's no server to run: friends open the page, type the 4-letter room code and join.

## Play

Open `index.html` in a browser, or host the repo on GitHub Pages (Settings → Pages → Deploy from a branch → `main` / root).

Controls: WASD to move, Shift to sprint, C to crouch, mouse to aim and shoot, R to reload, G for a grenade, V to knife, F to use an armory or hold to revive a squadmate, 4 to deploy an airstrike or sentry, N to start the next wave early, M for voice chat. Phones and tablets get on-screen controls.

 https://hartj77-blip.github.io/Wave-shooter/

## How it's built

Everything is in `index.html`: three.js r128 from cdnjs for rendering, procedural textures and synthesized sound, no build step. `peerjs.min.js` is a local copy of PeerJS 1.5 for co-op (the page falls back to jsDelivr if it's missing).

For local co-op testing, run a PeerJS server and open `http://localhost:8000/?peerServer=localhost:9000`.

### Co-op relay

Players normally connect directly. Some networks, mobile data especially, block that, and joining fails with "Couldn't connect to that room". A relay (TURN) server fixes it. Sign up for the free plan at [metered.ca](https://www.metered.ca/), then put your app name and API key into `RELAY` near the top of the networking code in `index.html`. The key is meant to be used from browsers, and Metered caps usage on the free plan.

## Versions

Every release stays playable. `index.html` is the latest build, `versions.html` lists the older ones, and each old build is a frozen copy in `versions/`. Before changing `index.html` for a new release, copy it to `versions/<n>-<name>.html`, add a card for it in `versions.html`, and bump `NET_PREFIX` in the new build so old and new co-op rooms don't mix.
