// Automated playtest: runs a solo game headlessly through several waves using
// the window.__holdout hook. The player is made invulnerable and enemies that
// get within range are "shot", like a player holding the square would.
// Checks waves advance, enemies spawn in valid places and none get stuck
// somewhere they can never be reached (which would stall the wave forever),
// and that dying and restarting gives a clean run.
//
//   npm i -g playwright && npx playwright install chromium   (once)
//   node tests/playtest.js
const path = require('path');
const http = require('http');
const fs = require('fs');
let chromium;
try { ({ chromium } = require('playwright')); } catch {
  console.log('Install Playwright first: npm i -g playwright && npx playwright install chromium');
  process.exit(1);
}
const ROOT = path.join(__dirname, '..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.glb': 'model/gltf-binary', '.jpg': 'image/jpeg', '.png': 'image/png', '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg' };
const server = http.createServer((req, res) => {
  const file = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/^\/$/, '/index.html'));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

function playWaves(maxWave) {
  const H = window.__holdout;
  const problems = [];
  document.getElementById('btnPlay').click();
  const P = H.player;
  const HOSTILE = { soldier: 1, elite: 1, dog: 1, jugg: 1 };
  const seen = new Map(); // enemy id -> { born, closest }
  let t = 0;
  const log = [];
  while (H.wave <= maxWave && t < 60 * 40) {
    P.invuln = 1e9;
    if (!P.alive || P.down) { problems.push('player went down while invulnerable'); break; }
    H.step(20, 0.05); t += 1;
    if (H.state !== 'playing') { problems.push(`state became ${H.state}`); break; }
    for (const e of H.ents) {
      if (!HOSTILE[e.type] || e.dead) continue;
      if (![e.x, e.z].every(Number.isFinite)) { problems.push(`${e.type} position is NaN`); e.hp = 0; }
      if (Math.abs(e.x) > 60 || Math.abs(e.z) > 60) problems.push(`${e.type} left the map at ${e.x.toFixed(1)},${e.z.toFixed(1)}`);
      const d = Math.hypot(e.x - P.x, e.z - P.z);
      const rec = seen.get(e.id) || { born: t, closest: 1e9, type: e.type };
      rec.closest = Math.min(rec.closest, d);
      seen.set(e.id, rec);
      // In range: the "player" shoots it.
      if (d < 24 && Math.random() < 0.25) H.hurtEnt(e, 1e7, 'head', 'bullet', P);
      else if (t - rec.born > 150) { problems.push(`wave ${H.wave}: ${e.type} never got closer than ${rec.closest.toFixed(1)} m in 150 s at ${e.x.toFixed(1)},${e.z.toFixed(1)}`); H.hurtEnt(e, 1e7, 'head', 'bullet', P); }
    }
    for (const e of H.ents) if (e.type === 'heli' && !e.friendly && !e.dead && Math.random() < 0.05) H.hurtEnt(e, 1e7, 'body', 'blast', P);
    if (H.phase === 'inter') { if (log[log.length - 1] !== H.wave) log.push(H.wave); H.interT = 0; }
  }
  if (H.wave <= maxWave) problems.push(`only reached wave ${H.wave} in ${t} s`);
  return { problems: [...new Set(problems)].slice(0, 12), waves: log, t, wave: H.wave };
}

(async () => {
  await new Promise((ok) => server.listen(0, ok));
  const url = `http://localhost:${server.address().port}/`;
  const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const page = await browser.newPage({ viewport: { width: 800, height: 500 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon|status of 404|Failed to load resource|peer/i.test(m.text())) errors.push(m.text()); });
  await page.goto(url);
  await page.waitForFunction(() => window.__holdout, null, { timeout: 120000 });
  let failed = 0;
  const report = (label, problems, extra) => {
    const all = problems.concat(errors.splice(0).map((e) => 'console: ' + e));
    if (all.length) { failed++; console.log(`  FAIL ${label}\n    ${all.join('\n    ')}`); } else console.log(`  ok  ${label}${extra ? ': ' + extra : ''}`);
  };
  const waves = Number(process.env.WAVES || 12);
  const r = await page.evaluate(playWaves, waves);
  report(`solo run through wave ${waves}`, r.problems, `cleared waves ${r.waves.join(', ')} in ${r.t} s of game time`);

  // Death and restart: the next run starts clean.
  const d = await page.evaluate(() => {
    const H = window.__holdout, P = H.player;
    P.invuln = 0; P.armor = 0;
    for (let i = 0; i < 400 && H.state === 'playing'; i++) { P.invuln = 0; H.hurt(50); H.step(2, 0.05); }
    const endState = H.state;
    document.getElementById('btnAgain').click();
    H.step(5, 0.05);
    const leftovers = H.ents.filter((e) => !e.dead && (e.type === 'soldier' || e.type === 'elite' || e.type === 'dog' || e.type === 'jugg')).length;
    return { endState, state: H.state, wave: H.wave, hp: P.hp, alive: P.alive, leftovers };
  });
  const dp = [];
  if (d.endState !== 'over') dp.push(`dying led to state ${d.endState}, not the game-over screen`);
  if (d.state !== 'playing' || !d.alive || d.wave > 1 || d.leftovers) dp.push('restart was not clean: ' + JSON.stringify(d));
  report('death, game over and restart', dp);

  await browser.close();
  server.close();
  console.log(failed ? `\n${failed} FAILED` : '\nall passed');
  process.exitCode = failed ? 1 : 0;
})();
