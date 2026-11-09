// Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
// Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import * as T from '/vendor/three-bundle.js';

const token = document.querySelector('meta[name=token]').content;
const $ = (id) => document.getElementById(id);
const BUILD = document.title;

async function api(path, body, method) {
  const opt = { method: method || (body === undefined ? 'GET' : 'POST'), headers: { 'X-Token': token } };
  if (body instanceof ArrayBuffer) { opt.body = body; }
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({ error: 'bad reply' }));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const f32 = (b64) => { const s = atob(b64); const u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); return new Float32Array(u.buffer); };

// ---- busy indicator with elapsed time (the server may take a few seconds on big models) ----
async function busy(text, promise) {
  const t0 = Date.now(); $('busy').hidden = false;
  const tick = () => { $('busytext').textContent = text + ' ' + Math.round((Date.now() - t0) / 1000) + ' s'; };
  tick(); const id = setInterval(tick, 500);
  try { return await promise; } finally { clearInterval(id); $('busy').hidden = true; }
}
const say = (t) => { $('statusbar').textContent = t + '   ·   ' + BUILD; };

// ---- 3D scene ----
const canvas = $('view');
const renderer = new T.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new T.Scene(); scene.background = new T.Color(0x0b1219);
const camera = new T.PerspectiveCamera(40, 1, 0.1, 5000); camera.up.set(0, 0, 1);
const controls = new T.OrbitControls(camera, canvas); controls.enableDamping = true;
scene.add(new T.HemisphereLight(0xffffff, 0x223344, 1.1));
const sun = new T.DirectionalLight(0xffffff, 1.4); sun.position.set(1, -2, 3); scene.add(sun);
camera.add(sun); scene.add(camera);
const grid = new T.GridHelper(400, 40, 0x22303c, 0x16212b); grid.rotation.x = Math.PI / 2; scene.add(grid);

let model = null, geo = null, colors = null;
const overlay = new T.Group(); scene.add(overlay);
let previewMesh = null; const regionMeshes = new Map();
let selId = null, selInfo = null, state = { mode: 'auto' };

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w * renderer.getPixelRatio() || canvas.height !== h * renderer.getPixelRatio()) {
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
}
(function loop() { requestAnimationFrame(loop); resize(); controls.update(); renderer.render(scene, camera); })();

function soupGeometry(arr) {
  const g = new T.BufferGeometry(); g.setAttribute('position', new T.BufferAttribute(arr, 3)); g.computeVertexNormals(); return g;
}
function clearOverlays() {
  for (const m of [...overlay.children]) { overlay.remove(m); m.geometry.dispose(); }
  previewMesh = null; regionMeshes.clear();
}
function setModel(res) {
  if (model) { scene.remove(model); geo.dispose(); }
  clearOverlays(); selId = null; selInfo = null;
  const arr = f32(res.soup);
  geo = soupGeometry(arr);
  colors = new Float32Array(arr.length).fill(0.58);
  geo.setAttribute('color', new T.BufferAttribute(colors, 3));
  model = new T.Mesh(geo, new T.MeshStandardMaterial({ vertexColors: true, flatShading: true, metalness: 0.1, roughness: 0.75 }));
  scene.add(model);
  const [lo, hi] = res.bbox, c = lo.map((v, i) => (v + hi[i]) / 2), size = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  controls.target.set(c[0], c[1], c[2]);
  camera.position.set(c[0] + size * 1.2, c[1] - size * 1.6, c[2] + size * 1.1);
  camera.near = size / 100; camera.far = size * 40; camera.updateProjectionMatrix();
  grid.position.set(c[0], c[1], lo[2]); grid.scale.setScalar(Math.max(1, size / 200));
  $('modelinfo').textContent = `${res.name} · ${res.triangles.toLocaleString()} triangles · ${(hi[0]-lo[0]).toFixed(1)} × ${(hi[1]-lo[1]).toFixed(1)} × ${(hi[2]-lo[2]).toFixed(1)} mm` + (res.seconds ? ` · loaded in ${res.seconds} s` : '');
  $('hint').textContent = 'Click a flat face or a cylinder on the model.';
  $('selinfo').textContent = 'Click the model.'; $('add').disabled = true; $('stats').textContent = '';
  refreshRegions(); say('Loaded ' + res.name);
}
function paint(tris, rgb) {
  for (let k = 0; k < colors.length; k++) colors[k] = 0.58;   // reset
  if (tris) for (const t of tris) for (let v = 0; v < 9; v += 3) { const o = t * 9 + v; colors[o] = rgb[0]; colors[o + 1] = rgb[1]; colors[o + 2] = rgb[2]; }
  geo.attributes.color.needsUpdate = true;
}
function addOverlay(soup, color, opacity) {
  const m = new T.Mesh(soupGeometry(f32(soup)), new T.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: T.DoubleSide }));
  overlay.add(m); return m;
}

// ---- opening files ----
async function openBuffer(buf, name) {
  try { setModel(await busy('Reading ' + name + '…', api('/api/load?name=' + encodeURIComponent(name), buf))); }
  catch (e) { alert(e.message); }
}
$('file').addEventListener('change', async (e) => { const f = e.target.files[0]; if (f) openBuffer(await f.arrayBuffer(), f.name); });
canvas.addEventListener('dragover', (e) => e.preventDefault());
canvas.addEventListener('drop', async (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) openBuffer(await f.arrayBuffer(), f.name); });
$('example').addEventListener('click', async () => {
  try { setModel(await busy('Loading example…', api('/api/example', {}))); } catch (e) { alert(e.message); }
});

// ---- picking ----
const ray = new T.Raycaster(); let down = null;
canvas.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerup', async (e) => {
  if (!down || !model) return;
  const moved = Math.hypot(e.clientX - down[0], e.clientY - down[1]); down = null;
  if (moved > 4) return;
  const r = canvas.getBoundingClientRect();
  ray.setFromCamera(new T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -(((e.clientY - r.top) / r.height) * 2 - 1)), camera);
  const hit = ray.intersectObject(model)[0];
  if (!hit) return;
  try {
    const res = await busy('Finding the surface…', api('/api/select', { tri: hit.faceIndex, mode: state.mode }));
    selId = res.sel_id; selInfo = res.info; paint(res.tris, [1.0, 0.66, 0.3]);
    const i = res.info;
    $('selinfo').innerHTML = i.kind === 'plane'
      ? `Flat face · ${i.triangles} triangles · wall here ≈ ${i.wall_mm ?? '?'} mm`
      : `${i.concave ? 'Hole' : 'Outer'} cylinder · radius ${i.radius} mm · length ${i.length} mm${i.partial_arc ? ' · partial (' + i.arc_deg + '°)' : ''} · wall ≈ ${i.wall_mm ?? '?'} mm`;
    $('planeopts').hidden = i.kind !== 'plane'; $('cylopts').hidden = i.kind !== 'cylinder';
    $('add').disabled = false; schedulePreview();
  } catch (err) { $('selinfo').textContent = err.message; }
});
for (const b of document.querySelectorAll('#modes button')) b.addEventListener('click', () => {
  document.querySelectorAll('#modes button').forEach((x) => x.classList.remove('on')); b.classList.add('on'); state.mode = b.dataset.mode;
});

// ---- options & preview ----
function params() {
  const p = { depth_mode: $('through').checked ? 'through' : 'fixed', depth_mm: +$('depth').value, density: +$('density').value, margin_mm: +$('margin').value };
  if (selInfo && selInfo.kind === 'plane') {
    p.window = { shape: $('shape').value, u0: $('u0').value / 100, u1: $('u1').value / 100, v0: $('v0').value / 100, v1: $('v1').value / 100 };
  } else if (selInfo) {
    p.axial = [$('a0').value / 100, $('a1').value / 100];
    if (+$('g0').value !== 0 || +$('g1').value !== 360) p.arc = [+$('g0').value, +$('g1').value];
  }
  return p;
}
let timer = null;
function schedulePreview() { clearTimeout(timer); timer = setTimeout(preview, 250); }
async function preview() {
  if (selId == null) return;
  try {
    const res = await api('/api/preview', { sel_id: selId, params: params() });
    if (previewMesh) { overlay.remove(previewMesh); previewMesh.geometry.dispose(); }
    previewMesh = addOverlay(res.soup, 0xfde047, 0.55);
    const s = res.stats;
    $('stats').innerHTML = `Region: ${s.depth_mm} mm deep${s.wall_mm ? ' (wall ' + s.wall_mm + ' mm + a little extra so it breaks through)' : ''} · ${s.triangles} triangles · ` +
      (s.closed ? '<span class="ok">closed solid ✓</span>' : '<span class="bad">NOT closed — slicer may ignore it</span>');
  } catch (e) { $('stats').innerHTML = '<span class="bad">' + e.message + '</span>'; }
}
document.querySelectorAll('#optcard input, #optcard select').forEach((el) => el.addEventListener('input', () => {
  $('depthrow').hidden = $('through').checked; schedulePreview();
}));
$('add').addEventListener('click', async () => {
  try {
    const res = await api('/api/add', { sel_id: selId, params: params() });
    if (previewMesh) { overlay.remove(previewMesh); previewMesh.geometry.dispose(); previewMesh = null; }
    regionMeshes.set(res.id, addOverlay(res.soup, 0x34d399, 0.6));
    paint(null); selId = null; $('add').disabled = true; $('selinfo').textContent = 'Added. Click another surface to add more.'; $('stats').textContent = '';
    refreshRegions(); say('Added ' + res.label);
  } catch (e) { alert(e.message); }
});

async function refreshRegions() {
  const list = await api('/api/regions').catch(() => []);
  const ul = $('regions'); ul.innerHTML = '';
  if (!list.length) ul.innerHTML = '<li class="muted">None yet.</li>';
  for (const r of list) {
    const li = document.createElement('li');
    li.innerHTML = `<span>${r.label} <span class="muted">· ${r.density}% gyroid</span></span>`;
    const b = document.createElement('button'); b.className = 'ghost'; b.textContent = 'Remove';
    b.onclick = async () => { await api('/api/remove', { id: r.id }); const m = regionMeshes.get(r.id); if (m) { overlay.remove(m); regionMeshes.delete(r.id); } refreshRegions(); };
    li.appendChild(b); ul.appendChild(li);
  }
  for (const id of ['xprusa', 'xorca', 'xstl']) $(id).disabled = !list.length;
}

// ---- export ----
async function download(flavor) {
  const q = `flavor=${flavor}&bed_x=${$('bedx').value}&bed_y=${$('bedy').value}&t=${encodeURIComponent(token)}`;
  const r = await fetch('/api/export?' + q, { headers: { 'X-Token': token } });
  if (!r.ok) { alert((await r.json()).error); return; }
  const name = /filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') || '')?.[1] || 'export';
  const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = name; a.click(); say('Saved ' + name);
}
$('xprusa').onclick = () => { $('bedx').value = 125; $('bedy').value = 105; download('prusa'); };
$('xorca').onclick = () => { if ($('bedx').value == 125) { $('bedx').value = 128; $('bedy').value = 128; } download('orca'); };
$('xstl').onclick = () => download('stl');

// ---- tabs, Cura, quit, ping ----
for (const t of document.querySelectorAll('.tab')) t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x === t));
  document.querySelectorAll('.tabpane').forEach((p) => { p.hidden = p.id !== 'tab-' + t.dataset.tab; });
  if (t.dataset.tab === 'cura') curaRefresh();
});
const esc = (t) => String(t).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
async function curaRefresh() {
  const box = $('curalist'); box.textContent = 'Looking for Cura…';
  try {
    const s = await api('/api/cura/status');
    if (!s.source_found) { box.innerHTML = '<span class="bad">The plug-in folder is missing next to this app.</span>'; return; }
    if (!s.copies.length) { box.innerHTML = 'No Cura settings folder found in:<br><code>' + s.roots.map(esc).join('<br>') + '</code><br>Start Cura once so it creates its folder, then press “Look again”.'; return; }
    box.innerHTML = '';
    for (const c of s.copies) {
      const d = document.createElement('div'); d.className = 'copy';
      d.innerHTML = `<b>Cura ${c.version}</b><br><span class="muted">${esc(c.config_dir)}</span><br>` +
        (c.installed ? (c.old_layout ? '<span class="bad">Old copy (Cura will not list it under Manage). Press Update to fix.</span>' :
          (c.in_sync ? '<span class="ok">Installed and identical to this version ✓</span>' : '<span class="bad">Installed but different from this version</span>')) : 'Not installed') +
        (c.installed && !c.old_layout ? '<br>' + (c.registered ? '<span class="ok">Listed in Cura’s package record (Marketplace › Manage) ✓</span>' : '<span class="bad">Not in Cura’s package record yet. Press Update.</span>') : '') +
        '<br>' + (c.log_state === 'loaded' ? '<span class="ok">Cura’s last run loaded it and its self-test passed ✓</span><br><span class="muted small">The log cannot prove Cura then stayed open; if Cura closed by itself, treat this as NOT confirmed.</span>' :
          c.log_state === 'crashed' ? '<span class="bad">NOT CONFIRMED: it loaded, then the log shows a crash.</span>' :
          (c.installed ? '<span class="muted">Start Cura once; then press “Look again” — its log will say whether it loaded.</span>' : '')) +
        (c.log_line && c.log_state !== 'loaded' ? '<br><span class="bad small">' + esc(c.log_line) + '</span>' : '');
      const row = document.createElement('div'); row.className = 'row';
      const inst = document.createElement('button'); inst.className = 'primary'; inst.textContent = c.installed ? 'Update' : 'Install';
      inst.onclick = async () => { try { const r = await api('/api/cura/install', { config_dir: c.config_dir }); alert(r.verified && r.registered ? 'Installed, read back OK and recorded in Cura’s package list. Restart Cura.' : 'Copied, but a check FAILED (read-back or package record).'); } catch (e) { alert(e.message); } curaRefresh(); };
      row.appendChild(inst);
      if (c.installed) { const un = document.createElement('button'); un.textContent = 'Uninstall'; un.onclick = async () => { await api('/api/cura/uninstall', { config_dir: c.config_dir }); curaRefresh(); }; row.appendChild(un); }
      d.appendChild(row); box.appendChild(d);
    }
  } catch (e) { box.textContent = e.message; }
}
$('curarefresh').onclick = curaRefresh;
$('quit').onclick = async () => { try { await api('/api/quit'); } catch (e) {} document.body.innerHTML = '<p style="padding:30px">Gyroid Filter has stopped. You can close this tab.</p>'; };
setInterval(() => api('/api/ping').catch(() => {}), 5000); api('/api/ping').catch(() => {});
say('Ready');
window.__gf = { camera, controls, get model() { return model; }, THREE: T };   // used by tools/screenshots.py
