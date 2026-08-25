#!/usr/bin/env node
/**
 * Record a playtest of any A3Game three.js project.
 *
 * **Not** screen recording: WebGL runs on SwiftShader here, so real-time
 * capture yields slow motion. Instead the simulation is driven at a fixed
 * timestep via `A3GameRuntimeHost.tick(forcedDelta)`, one image is captured per
 * step, and the result is encoded at that rate — smooth however long each frame
 * actually took.
 *
 * Five things were each found the hard way. See `## Playtest` in
 * `agent_skills/engine_context/three_js_api.md` for the measurements:
 *
 *   1. Stop the host's rAF loop, tick *inside* a `requestAnimationFrame`, and
 *      wait one further frame before capturing — otherwise the compositor never
 *      commits and each screenshot blocks ~1.25 s (1335 vs 355 ms/frame).
 *   2. Capture via raw CDP `Page.captureScreenshot`; `page.screenshot()` waits
 *      for stability a stopped rAF loop never reaches.
 *   3. Deliver **real events** — keys to `window`, pointer to `host.container`,
 *      aiming through `setLook`. Nothing reaches in and moves an entity, or the
 *      video would be evidence of nothing.
 *   4. Treat a renderer crash as "the video is as long as it is": keep and
 *      report partial frames rather than losing the take.
 *   5. `libopenh264` is bitrate-driven (no libx264), and `-start_number` stops
 *      ffmpeg halting at the first gap.
 *
 * Nothing here is game-specific. What varies — which verbs are held, whether
 * the camera can be swept, how long the opening ceremony lasts, what stays
 * pressed throughout — is read from the running game or supplied by a plan.
 * See `DISCOVERY` and `--action-plan`.
 */

import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 1) {
    if (!argv[i].startsWith('--')) continue;
    out[argv[i].slice(2)] = argv[i + 1];
    i += 1;
  }
  return out;
}

const args = parseArgs(process.argv);
for (const key of ['url', 'output-dir', 'duration', 'fps', 'width', 'height']) {
  if (!args[key]) throw new Error(`Missing --${key}`);
}
const outputDir = path.resolve(args['output-dir']);
const framesDir = path.join(outputDir, 'frames');
const reportPath = path.join(outputDir, 'report.json');
const FPS = Number(args.fps);
const DT = 1 / FPS;
const duration = Number(args.duration);
const width = Number(args.width);
const height = Number(args.height);
if (![FPS, duration, width, height].every((n) => Number.isFinite(n) && n > 0)) {
  throw new Error('duration, fps, width, and height must be positive numbers');
}

const report = {
  schema_version: 'a3game.playtest_report.v1',
  engine: 'three_js',
  status: 'failed',
  url: args.url,
  output_dir: outputDir,
  fps: FPS,
  requested_seconds: duration,
  viewport: { width, height },
  action_source: '',
  look_mode: '',
  warmup_seconds: 0,
  sustained: [],
  excluded_actions: [],
  actions: [],
  executed_actions: [],
  frames: 0,
  recorded_seconds: 0,
  fixed_tick: false,
  crash: '',
  page_errors: [],
  console_errors: [],
  warnings: [],
  video: null,
  game_state: null,
};

const write = () => writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);

/**
 * Ask the running game what can be done in it, and how.
 *
 * Returns a whole *recording plan*, not just a list of verbs, because three of
 * the four things that vary between games are not per-action:
 *
 * - `sustained` — what stays pressed for the entire take. A racer whose throttle
 *   is released between actions records a car twitching on the start line; the
 *   throttle is the condition everything else is demonstrated under.
 * - `warmup` — how long to tick before capturing. Games open on a countdown or a
 *   spawn, and a brawler drops attacks until its round reaches FIGHT.
 * - `look` — whether sweeping the camera is meaningful. A side-scroller derives
 *   its camera from the fighters and ignores a sweep; under drag-look a sweep
 *   fights the game's own framing.
 *
 * Sources, in order of how much each knows about *this* game; whichever answered
 * is reported as `action_source`:
 *
 *   1. `__A3GAME_PLAYTEST__` — the game declares its own plan. Strictly better
 *      than anything inferred: only the game knows where its enemies are.
 *   2. `input.actionBindings` — the game's own verbs (fire, handbrake, draw).
 *      Authoritative, because it is the table the running game dispatches on.
 *   3. `input.keyBindings` — movement, deduplicated by action: the defaults bind
 *      `KeyW` *and* `ArrowUp` to `forward`.
 *   4. `[data-game-action]` elements — menu-driven games.
 *   5. A generic keyboard plan, so an unannotated game still gets a playtest.
 *
 * A binding's *code* is sent, not a character: `A3GameInputRouter` reads
 * `event.code`, which is also what Playwright accepts.
 */
const DISCOVERY = () => {
  const game = globalThis.__A3GAME_GAME__;
  const input = game?.input;

  // Held vs tapped is a property of the verb, and getting it wrong records a
  // game that appears not to respond. One frame of `forward` moves a character
  // by centimetres; a charge-and-release verb (draw a bow, hold a guard, hold a
  // handbrake) does nothing at all if released the same frame. Conversely a
  // discrete verb must be released, or a semi-automatic weapon never fires
  // twice and a held key auto-repeats forever.
  //
  // Matching is substring-based, so `move_forward`, `sprintToggle` and
  // `holdBlock` all land here. Anything unmatched is treated as a tap, which is
  // the safe default: a tapped hold under-demonstrates, but a held tap can
  // auto-repeat an entire magazine or spam a menu.
  const HELD = new RegExp([
    // translation, including vehicle/aircraft axes and free-fly
    'forward|back|left|right|up|down|strafe|ascend|descend|thrust|yaw|pitch|roll',
    // locomotion modes and postures
    'run|walk|sprint|dash|crouch|sneak|prone|slide|swim|climb|hover|fly|glide',
    // driving
    'accel|throttle|brake|boost|nitro|nos|drift|gas|handbrake|ebrake|clutch',
    // charge-and-release, and anything whose value is the interval it is held
    'draw|charge|aim|zoom|scope|focus|hold|pull|push|drag|carry|grab|grapple',
    // defensive holds
    'block|guard|defend|shield|parry|brace|cover',
    // sustained fire and tools
    'auto|spray|beam|burn|heal|repair|mine|dig|build|paint|spray',
    // sustained interaction: a progress bar is held, not tapped
    'interact|use|open|channel|cast|revive|capture|hack|lockpick',
    // camera / turret sweeps
    'look|turn|pan|orbit|lean|peek|freelook',
  ].join('|'), 'i');

  // Verbs that read as held by the rule above but are discrete in practice, so
  // they are matched first and win. `toggle*` is the common shape: a toggled
  // sprint or crouch is a single press, and holding it flips state every frame.
  const TAPPED = /toggle|switch|cycle|next|prev|swap|select|equip|holster|sheathe|reload|jump|hop|dodge|roll_dodge|evade|blink|teleport|respawn|reset|restart|pause|menu|map|inventory|emote|taunt|horn|light|flash/i;

  const isHeld = (action) => !TAPPED.test(action) && HELD.test(action);

  const asPlan = (source, actions, extra = {}) => ({ source, actions, ...extra });

  const declared = (() => {
    const exposed = globalThis.__A3GAME_PLAYTEST__ ?? game?.playtestActions;
    let value = exposed?.actions ?? exposed;
    try { if (typeof value === 'function') value = value(); } catch { return null; }
    if (!Array.isArray(value) || !value.length) return null;
    return asPlan('declared', value, {
      sustained: exposed?.sustained ?? exposed?.hold,
      warmup: exposed?.warmup,
      look: exposed?.look,
    });
  })();
  if (declared) return declared;

  const actions = [];
  const seen = new Set();
  const push = (id, extra) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    actions.push({ id, label: id, ...extra });
  };
  const bind = (code, action) => {
    if (/^Mouse0$/i.test(code)) push(action, { mouse: true, hold: isHeld(action) });
    else if (/^Mouse/i.test(code)) return;            // only button 0 is emulable
    else if (isHeld(action)) push(action, { keys: [code] });
    else push(action, { taps: [code] });
  };
  // Game verbs first: they are what distinguishes this game from any other.
  for (const [code, action] of Object.entries(input?.actionBindings ?? {})) bind(code, action);
  for (const [code, action] of Object.entries(input?.keyBindings ?? {})) bind(code, action);

  if (actions.length) {
    // A game whose forward motion *is* the game — anything with a throttle —
    // needs it held under everything else rather than demonstrated in turn. The
    // tell is a vehicle-shaped verb alongside something only a vehicle has.
    const drive = actions.find((item) => /^(accel\w*|throttle|gas|forward)$/i.test(item.id));
    const vehicular = /brake|handbrake|ebrake|drift|steer|clutch|nitro|nos|respawn|lap|gear/i;
    const sustained = drive && actions.some((item) => vehicular.test(item.id))
      ? [drive.id]
      : [];
    return asPlan('input_router', actions, { sustained });
  }

  const dom = [...document.querySelectorAll('[data-game-action]')]
    .map((node) => ({
      id: node.getAttribute('data-game-action'),
      label: node.getAttribute('aria-label') || node.textContent?.trim() || '',
      click: '[data-game-action="' + CSS.escape(node.getAttribute('data-game-action') || '') + '"]',
    }))
    .filter((item) => item.id);
  if (dom.length) return asPlan('dom', dom);

  return asPlan('fallback', [
    { id: 'forward', keys: ['KeyW'] },
    { id: 'left', keys: ['KeyA'] },
    { id: 'right', keys: ['KeyD'] },
    { id: 'jump', taps: ['Space'] },
    { id: 'primary', mouse: true },
  ]);
};

/** Map an action name back to the key code that triggers it, for `sustained`. */
const RESOLVE = (names) => {
  const input = globalThis.__A3GAME_GAME__?.input;
  const table = { ...(input?.keyBindings ?? {}), ...(input?.actionBindings ?? {}) };
  return names.map((name) => {
    if (/^(Key|Digit|Arrow|Numpad|F\d)/.test(name) || /^(Space|Shift|Control|Alt|Tab|Enter|Escape)/.test(name)) {
      return { name, code: name };                     // already a code
    }
    const code = Object.entries(table).find(([, action]) => action === name)?.[0];
    return { name, code: code && !/^Mouse/i.test(code) ? code : null };
  });
};

function normalize(raw, source, budgetSeconds) {
  const actions = raw
    .filter((item) => item && typeof item === 'object')
    .map((item, index) => ({
      id: String(item.id ?? item.name ?? `${source}_${index + 1}`),
      label: String(item.label ?? item.id ?? ''),
      keys: (Array.isArray(item.keys) ? item.keys : []).map(String),
      taps: (Array.isArray(item.taps) ? item.taps : []).map(String),
      mouse: Boolean(item.mouse),
      hold: Boolean(item.hold),
      click: typeof item.click === 'string' ? item.click : '',
      seconds: Number(item.duration ?? item.seconds) > 0 ? Number(item.duration ?? item.seconds) : 0,
      source,
    }));
  // Share the take evenly when nothing declared a length, then clamp the whole
  // plan to the requested duration: a discovered plan has no idea how long the
  // caller asked for, and a bounded recording is the contract.
  const share = Math.max(0.4, budgetSeconds / Math.max(1, actions.length));
  let remaining = budgetSeconds;
  const planned = [];
  for (const action of actions) {
    if (remaining <= 0) break;
    const seconds = Math.min(action.seconds || share, remaining);
    remaining -= seconds;
    planned.push({ ...action, seconds });
  }
  return planned;
}

const require_ = createRequire(
  path.join(path.resolve(args['playwright-root'] || process.cwd()), 'package.json'),
);
let chromium;
try {
  ({ chromium } = require_('playwright'));
} catch (error) {
  throw new Error(
    `playwright must be installed in --playwright-root (${args['playwright-root'] || process.cwd()}): ${error.message}`,
  );
}

await mkdir(outputDir, { recursive: true });
await rm(framesDir, { recursive: true, force: true });
await mkdir(framesDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: args['browser-executable'] || undefined,
  // None of these is decoration. This box has NVIDIA cards with no render node
  // and no display, so Chromium finds a GPU, tries it, and fails *without*
  // falling back to software; of five documented combinations only this one
  // reaches SwiftShader. `--in-process-gpu` is required (without it there is no
  // WebGL context at all), and it is also why `CDPScreenshotNewSurface` — which
  // Playwright enables by default — must be off: together they kill the renderer
  // after 40-60 screenshots, with no separate GPU process left to restart.
  args: [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu-watchdog',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--in-process-gpu',
    '--override-use-software-gl-for-tests',
    '--disable-features=CDPScreenshotNewSurface',
  ],
});
const page = await browser.newPage({ viewport: { width, height } });
page.on('pageerror', (error) => report.page_errors.push(String(error.message || error).slice(0, 200)));
page.on('console', (message) => {
  if (message.type() === 'error') report.console_errors.push(message.text().slice(0, 200));
});

const held = new Set();
const tapped = [];

try {
  await page.goto(args.url, { waitUntil: 'load', timeout: 120_000 });
  const booted = await page
    .waitForFunction(() => globalThis.__A3GAME_GAME__ !== undefined, { timeout: 120_000 })
    .then(() => true)
    .catch(() => false);
  if (!booted) report.warnings.push('__A3GAME_GAME__ never appeared; recorded the page as-is.');
  // Imported meshes resolve after boot, so the opening frames would otherwise
  // show a scene still wearing its procedural stand-ins.
  await page.waitForTimeout(3_000);

  const runtime = await page.evaluate(() => {
    const game = globalThis.__A3GAME_GAME__;
    const host = game?.host;
    if (typeof host?.tick !== 'function') return { fixedTick: false, lookMode: '', yaw: 0, pitch: 0 };
    host.stop?.();   // take over the frame loop; see the file header
    // Pointer lock needs a real gesture, which a synthetic pointerdown is not,
    // so a first-person game would sit under its own "click to lock" prompt for
    // the whole video. Clean up the take, never the game — a result banner still
    // re-shows itself through onStateChanged.
    try { game.hud?.setVisible?.('banner', false); } catch { /* no HUD */ }
    return {
      fixedTick: true,
      lookMode: String(game?.input?.lookMode ?? ''),
      // The game's own opening framing. A sweep starts from here, not from zero,
      // or it throws away a deliberate choice.
      yaw: Number(game?.input?.yaw ?? 0),
      pitch: Number(game?.input?.pitch ?? 0),
    };
  });
  report.fixed_tick = runtime.fixedTick;
  if (!runtime.fixedTick) {
    report.warnings.push('No host.tick(): captured wall-clock frames, which on SwiftShader look like slow motion.');
  }

  let plan = null;
  if (args['action-plan']) {
    const planPath = path.resolve(args['action-plan']);
    const parsed = JSON.parse(await readFile(planPath, 'utf8'));
    plan = Array.isArray(parsed)
      ? { source: 'plan', actions: parsed }
      : { ...parsed, source: 'plan', actions: parsed.actions ?? [] };
    report.action_plan = planPath;
  }
  const discovered = plan ?? (await page.evaluate(DISCOVERY));
  report.action_source = discovered.source;
  if (discovered.source === 'fallback') {
    report.warnings.push('Game published no bindings; recorded a generic keyboard smoke plan.');
  }

  // Sweeping the camera is meaningful only where the game reads it. Under
  // drag-look it fights the game's own framing, and a side-scroller derives the
  // camera from its fighters and ignores it outright.
  const lookArg = String(args.look ?? discovered.look ?? 'auto').toLowerCase();
  report.look_mode = lookArg !== 'auto'
    ? lookArg
    : (runtime.lookMode === 'drag' || !runtime.lookMode ? 'off' : 'pan');

  // Ceremony before play: countdowns, spawn-ins, a brawler that drops attacks
  // until its round reaches FIGHT. Ticked, not captured.
  const warmup = Math.max(0, Number(args.warmup ?? discovered.warmup ?? 0));

  const sustainedNames = (args.hold ? args.hold.split(',') : discovered.sustained ?? [])
    .map((item) => String(item).trim())
    .filter(Boolean);
  const sustained = sustainedNames.length ? await page.evaluate(RESOLVE, sustainedNames) : [];
  const sustainedCodes = sustained.filter((item) => item.code).map((item) => item.code);
  for (const item of sustained) {
    if (!item.code) report.warnings.push(`Cannot hold "${item.name}": no key binding for it.`);
  }
  report.sustained = sustainedCodes;

  // A sustained input states the take's premise, which constrains what can be
  // demonstrated inside it:
  //
  //  - The held action itself is not one of the things being shown.
  //  - Anything that *negates* the premise cannot be shown either. Reverse under
  //    a held throttle demonstrates neither; the measured result was a car
  //    crawling at 18 km/h in last place. Dropped, and named in the report.
  //  - Anything that discards progress is moved to the end rather than dropped.
  //    A respawn is worth seeing; a respawn one second in throws away the run.
  const ANTAGONIST = [
    [/^(forward|accel\w*|throttle|gas|boost|nitro|nos)$/i,
     /^(back\w*|reverse|brake|handbrake|ebrake|decel\w*|clutch)$/i],
    [/^(draw|charge|aim|zoom|scope|focus)$/i, /^(holster|sheathe|cancel|swap|equip)$/i],
    [/^(block|guard|defend|shield|brace|cover)$/i, /^(dodge|roll|evade|blink)$/i],
    [/^(sneak|crouch|prone|walk)$/i, /^(run|sprint|dash|jump)$/i],
    [/^(interact|use|channel|cast|revive|capture|hack|lockpick)$/i,
     /^(cancel|dodge|roll|jump)$/i],
  ];
  const negates = (name) => sustainedNames.some((holdName) =>
    ANTAGONIST.some(([a, b]) =>
      (a.test(holdName) && b.test(name)) || (b.test(holdName) && a.test(name))));
  const DISRUPTIVE = /^(respawn|reset|restart|retry|suicide|pause|menu|quit|exit)$/i;

  const excluded = [];
  const sequence = [];
  const deferred = [];
  for (const item of discovered.actions ?? []) {
    const name = String(item.id ?? item.name ?? '');
    if (sustainedNames.includes(name)) continue;
    if (negates(name)) { excluded.push(name); continue; }
    (DISRUPTIVE.test(name) ? deferred : sequence).push(item);
  }
  report.excluded_actions = excluded;
  if (excluded.length) {
    report.warnings.push(
      `Dropped ${excluded.join(', ')}: cannot be demonstrated while holding ${sustainedNames.join(', ')}.`,
    );
  }
  report.actions = normalize([...sequence, ...deferred], discovered.source, duration);
  if (!report.actions.length && !sustainedCodes.length) throw new Error('No actions to record');

  const cdp = await page.context().newCDPSession(page);
  let frame = 0;

  async function setKeys(wanted) {
    const target = new Set([...wanted, ...sustainedCodes]);
    for (const key of [...held]) {
      if (!target.has(key)) { await page.keyboard.up(key); held.delete(key); }
    }
    for (const key of target) {
      if (!held.has(key)) { await page.keyboard.down(key); held.add(key); }
    }
  }
  const setMouse = (down) =>
    page.evaluate((isDown) => {
      const element = globalThis.__A3GAME_GAME__?.host?.container ?? document.body;
      element.dispatchEvent(new PointerEvent(isDown ? 'pointerdown' : 'pointerup', {
        bubbles: true, button: 0, buttons: isDown ? 1 : 0, isPrimary: true,
      }));
    }, down);

  // Advance the simulation one fixed step and capture it. The tick runs inside
  // a rAF and the capture waits one more, so the compositor has committed a
  // frame before the screenshot is asked for.
  async function step(capture) {
    await page.evaluate((dt) => new Promise((resolve) => {
      const host = globalThis.__A3GAME_GAME__?.host;
      requestAnimationFrame(() => {
        if (typeof host?.tick === 'function') host.tick(dt);
        requestAnimationFrame(resolve);
      });
    }), DT);
    if (!capture) return;
    const shot = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 86 });
    await writeFile(
      path.join(framesDir, `f${String(frame).padStart(5, '0')}.jpg`),
      Buffer.from(shot.data, 'base64'),
    );
    frame += 1;
  }

  // Sweep relative to where the game chose to look, never absolute.
  const pan = (index) =>
    report.look_mode !== 'pan'
      ? Promise.resolve()
      : page.evaluate(([i, yaw0, pitch0]) => {
          const input = globalThis.__A3GAME_GAME__?.input;
          if (typeof input?.setLook === 'function') {
            input.setLook(yaw0 + i * 0.012, pitch0 + Math.sin(i * 0.03) * 0.12);
          }
        }, [index, runtime.yaw, runtime.pitch]).catch(() => {});

  if (warmup > 0) {
    await setKeys([]);   // sustained inputs apply from the warmup onward
    for (let i = 0; i < Math.round(warmup * FPS); i += 1) await step(false);
    report.warmup_seconds = warmup;
  }

  const started = Date.now();
  for (const action of report.actions) {
    const steps = Math.max(1, Math.round(action.seconds * FPS));
    const record = { id: action.id, source: action.source, frames: 0, ok: true };
    try {
      if (action.click) await page.locator(action.click).first().click({ timeout: 2_000 });
      if (action.keys.length) await setKeys(action.keys);
      else await setKeys([]);
      if (action.mouse) await setMouse(true);
      // A charge-and-release verb is held for its whole slot and released at the
      // end — that release *is* the shot. A discrete verb gets one frame on the
      // key: held longer it auto-repeats, and a semi-automatic weapon will not
      // fire a second time without the release.
      for (const key of action.taps) { await page.keyboard.down(key); if (!action.hold) tapped.push(key); }
      for (let i = 0; i < steps; i += 1) {
        await pan(frame);
        await step(true);
        record.frames += 1;
        while (tapped.length) await page.keyboard.up(tapped.pop());
      }
      if (action.hold) for (const key of action.taps) await page.keyboard.up(key).catch(() => {});
      if (action.mouse) await setMouse(false);
    } catch (error) {
      record.ok = false;
      record.error = String(error.message || error).split('\n')[0].slice(0, 160);
      report.crash = record.error;
    }
    report.executed_actions.push(record);
    if (report.crash) break;   // renderer is gone; keep what was captured
  }
  // Release anything still down, so a crashed take cannot leave a key pressed.
  for (const key of [...held]) await page.keyboard.up(key).catch(() => {});
  while (tapped.length) await page.keyboard.up(tapped.pop()).catch(() => {});

  report.frames = frame;
  report.recorded_seconds = Number((frame / FPS).toFixed(2));
  report.ms_per_frame = frame ? Math.round((Date.now() - started) / frame) : 0;
  report.game_state = await page
    .evaluate(() => globalThis.__A3GAME_GAME__?.getState?.() ?? null)
    .catch(() => null);

  if (frame >= 8) {
    // Input rate is the *simulation* rate, so the video plays at the right
    // speed however long each frame took to render. libopenh264 is what this
    // ffmpeg has, and it is bitrate-driven: no -crf, no -preset.
    const video = path.join(outputDir, 'video.mp4');
    const encoded = spawnSync(
      process.env.A3GAME_PLAYTEST_FFMPEG || process.env.FFMPEG || 'ffmpeg',
      ['-y', '-loglevel', 'error', '-start_number', '0', '-r', String(FPS),
       '-i', path.join(framesDir, 'f%05d.jpg'), '-c:v', 'libopenh264',
       '-b:v', process.env.A3GAME_PLAYTEST_BITRATE || '2500k',
       '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
       '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', video],
      { encoding: 'utf8' },
    );
    if (encoded.status === 0) report.video = video;
    else report.warnings.push(`Video encoding failed: ${encoded.error?.message || encoded.stderr?.trim() || `exit ${encoded.status}`}`);
  } else {
    report.warnings.push(`Only ${frame} frames captured; too few to encode.`);
  }
  report.status = report.frames > 0 ? 'completed' : 'failed';
} finally {
  await browser.close().catch(() => {});
  await write();
}
