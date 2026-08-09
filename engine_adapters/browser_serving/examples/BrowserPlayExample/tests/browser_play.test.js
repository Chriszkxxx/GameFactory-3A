const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "app.js"), "utf8");
const launcher = fs.readFileSync(path.join(root, "launch.cmd"), "utf8");
const manifest = JSON.parse(
  fs.readFileSync(
    path.join(root, "browser_play_manifest.json"),
    "utf8",
  ),
);

assert.equal(
  manifest.schema_version,
  "aaagameforge.browser_play_manifest.v1",
);
assert.equal(manifest.engine, "selected_by_packet");
assert.equal(manifest.gateway_route, "/game");
assert.equal(manifest.session_bootstrap.mode, "create_or_recover");
assert.equal(manifest.session_bootstrap.health_path, "/api/health");
assert.equal(manifest.session_bootstrap.create_path, "/api/sessions");
assert.equal(
  manifest.session_bootstrap.recover_path,
  "/api/sessions/recover",
);
assert.equal(manifest.streaming.session_url_field, "stream_url");
assert.equal(manifest.streaming.external_frontend, false);

assert.match(html, /id="streamFrame"/);
assert.match(html, /allow="[^"]*pointer-lock/);
assert.match(html, /id="focusButton"/);
assert.match(html, /id="retryButton"/);
assert.match(html, /id="fullscreenButton"/);
assert.doesNotMatch(
  html,
  /health|ammo|score|inventory|minimap|objective/i,
);

assert.match(script, /request\("\/api\/health"\)/);
assert.match(script, /request\("\/api\/sessions"/);
assert.match(script, /request\("\/api\/sessions\/recover"/);
assert.match(script, /method:\s*"POST"/);
assert.match(script, /stream_url/);
assert.match(script, /requestFullscreen/);
assert.match(script, /sessionStorage/);

assert.match(launcher, /A3GAME_BROWSER_PLAY_DIR/);
assert.match(launcher, /engine_adapters\.browser_serving gateway/);

console.log("Browser Play Example checks passed");
