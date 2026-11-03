/* Puppet stage engine (pilot).
   Beam writes the art: bone drawing code, poses, background layers, beats.
   This engine owns the skeleton, the timeline and the checks, so a head cannot
   come off a body, and every frame is a pure function of time. */
(function (root) {
  'use strict';
  const W = 390, H = 520, OVER = 30, PR = 2, R = 0.5;
  const FW = W * R, FH = H * R, OX = 98, OY = 130; // report frame inside the mask canvas
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const EASE = {
    linear: t => t, in: t => t * t, out: t => 1 - (1 - t) * (1 - t),
    inOut: t => t * t * (3 - 2 * t),
    back: t => { const c = 1.70158; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
    anticipate: t => { const c = 1.70158; return t * t * ((c + 1) * t - c); },
  };
  const mk = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
  const seeded = s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const lum = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;

  const S = { chars: {}, layers: [], ground: [[-30, 440], [420, 440]], anchors: {}, stage: { duration: 12, start: {}, beats: [] } };
  let runtimeErrors = [];
  const noteErr = m => { if (runtimeErrors.length < 12 && !runtimeErrors.includes(m)) runtimeErrors.push(m); };

  function groundY(x) {
    const g = S.ground;
    if (x <= g[0][0]) return g[0][1];
    for (let i = 1; i < g.length; i++) if (x <= g[i][0]) { const [a, b] = g[i - 1], [c, d] = g[i]; return lerp(b, d, (x - a) / ((c - a) || 1)); }
    return g[g.length - 1][1];
  }

  /* ---------- characters ---------- */
  function buildChar(c) {
    const errs = [], names = new Set(c.bones.map(b => b.name));
    const roots = c.bones.filter(b => !b.parent);
    if (roots.length !== 1) errs.push(`need exactly one root bone, found ${roots.length}`);
    for (const b of c.bones) {
      if (b.parent && !names.has(b.parent)) errs.push(`bone ${b.name}: parent ${b.parent} does not exist`);
      if (!Array.isArray(b.pivot) || b.pivot.length !== 2) { errs.push(`bone ${b.name}: pivot must be [x,y]`); b.pivot = [0, 0]; }
      b.rest = b.rest || 0; b.z = b.z || 0;
      try { b.fn = new Function('ctx', 'f', b.code || ''); } catch (e) { b.fn = () => {}; errs.push(`bone ${b.name} does not compile: ${e.message}`); }
    }
    c.order = []; const seen = new Set(); let go = true;
    while (go) { go = false; for (const b of c.bones) { if (seen.has(b.name)) continue; if (!b.parent || seen.has(b.parent)) { c.order.push(b); seen.add(b.name); go = true; } } }
    if (c.order.length !== c.bones.length) errs.push('bone parents form a cycle or a broken chain');
    c.drawList = [...c.order].sort((a, b) => a.z - b.z);
    return errs;
  }
  function matrices(c, ang) {
    const m = {};
    for (const b of c.order) {
      const p = b.parent ? m[b.parent] : new DOMMatrix();
      let x = b.pivot[0], y = b.pivot[1];
      if (!b.parent) { x += ang._x || 0; y += ang._y || 0; }
      m[b.name] = DOMMatrix.fromMatrix(p).translate(x, y).rotate(b.rest + (ang[b.name] || 0));
    }
    return m;
  }
  function drawChar(ctx, c, ang, face, only) {
    const base = ctx.getTransform(), M = matrices(c, ang);
    for (const b of c.drawList) {
      if (only && !only.includes(b.name)) continue;
      ctx.save(); ctx.setTransform(base.multiply(M[b.name]));
      try { b.fn(ctx, face); } catch (e) { noteErr(`${c.id}.${b.name}: ${e.message}`); }
      ctx.restore();
    }
  }
  const poseOf = (c, name) => ({ ...((c.poses || {})[name] || {}) });

  const charOf = id => S.chars[(S.stage.start[id] || {}).char || id];
  /* ---------- timeline: pure function of t ---------- */
  function actorState(id, t) {
    const st = S.stage, s0 = st.start[id] || {}, c = charOf(id);
    const cur = { x: s0.x ?? 195, lift: s0.lift ?? 0, scale: s0.scale ?? 1, facing: s0.facing ?? 1, opacity: s0.opacity ?? 1, angles: poseOf(c, s0.pose), face: { blink: 0, mouth: 'smile', look: 0, brow: 0, ...(s0.face || {}) }, clip: s0.clip || null, z: s0.z ?? 0, exiting: !!s0.exiting };
    let arc = 0, bob = 0, sq = 0, over = null, overW = 0;
    const beats = st.beats.filter(b => b.actor === id).sort((a, b) => a.at - b.at);
    for (const b of beats) {
      if (t < b.at) break;
      const d = Math.max(0.001, b.dur ?? 0.001), p = clamp((t - b.at) / d), e = (EASE[b.ease] || EASE.inOut)(p);
      if (b.move_to != null) cur.x = lerp(cur.x, b.move_to, e);
      if (b.lift_to != null) cur.lift = lerp(cur.lift, b.lift_to, e);
      if (b.scale_to != null) cur.scale = lerp(cur.scale, b.scale_to, e);
      if (b.opacity_to != null) cur.opacity = lerp(cur.opacity, b.opacity_to, e);
      if (b.facing != null) cur.facing = lerp(cur.facing, b.facing, EASE.inOut(clamp((t - b.at) / 0.18)));
      if (b.pose) { const tgt = poseOf(c, b.pose), keys = new Set([...Object.keys(cur.angles), ...Object.keys(tgt)]); for (const k of keys) cur.angles[k] = lerp(cur.angles[k] || 0, tgt[k] || 0, e); }
      if (b.face) Object.assign(cur.face, b.face);
      if (b.clip !== undefined) cur.clip = b.clip;
      if (b.exiting != null) cur.exiting = !!b.exiting;
      if (b.z != null) cur.z = b.z;
      if (t <= b.at + d) {
        if (b.arc) arc += b.arc * 4 * p * (1 - p);
        if (b.squash) sq += b.squash * Math.sin(Math.PI * p);
        if (b.cycle) {
          const A = poseOf(c, b.cycle[0]), B = poseOf(c, b.cycle[1]), u = 0.5 + 0.5 * Math.sin(2 * Math.PI * (b.hz || 2) * (t - b.at));
          overW = Math.min(1, (t - b.at) / 0.12, (b.at + d - t) / 0.12); over = {};
          for (const k of new Set([...Object.keys(A), ...Object.keys(B)])) over[k] = lerp(A[k] || 0, B[k] || 0, u);
          bob += (b.bob || 0) * Math.abs(Math.sin(2 * Math.PI * (b.hz || 2) * (t - b.at)));
        }
      }
    }
    const angles = { ...cur.angles };
    if (over) for (const k of new Set([...Object.keys(angles), ...Object.keys(over)])) angles[k] = lerp(angles[k] || 0, over[k] ?? angles[k] ?? 0, overW);
    const face = { ...cur.face, t };
    if (!face.blink && ((t + id.length * 0.9) % 3.7) < 0.13) face.blink = 1;
    const breath = 1 + 0.007 * Math.sin(t * 2.1 + id.length);
    const sy = (1 + sq) * breath, sx = 1 / (1 + sq);
    return { ...cur, angles, face, y: groundY(cur.x) - cur.lift - arc - bob, sx, sy, arc, baseY: groundY(cur.x) };
  }
  function clipPath(ctx, name, cam) {
    const a = S.anchors[name]; if (!a) return;
    const p = new Path2D();
    p.rect(-1000, -1000, 2400, 1000 + a.y);
    p.ellipse(a.x + cam, a.y, a.rx, a.ry, 0, 0, Math.PI * 2);
    ctx.clip(p);
  }
  function drawActor(ctx, id, t, cam) {
    const s = actorState(id, t);
    if (s.opacity <= 0.01) return s;
    ctx.save();
    if (s.clip) clipPath(ctx, s.clip, 0);
    ctx.globalAlpha = s.opacity;
    ctx.translate(s.x + cam, s.y); ctx.scale(s.scale * s.facing * s.sx, s.scale * s.sy);
    if (Math.abs(s.facing) < 0.02) ctx.scale(1, 1);
    drawChar(ctx, charOf(id), s.angles, s.face);
    ctx.restore();
    return s;
  }
  const actorsByZ = t => Object.keys(S.stage.start).filter(id => charOf(id)).map(id => [id, actorState(id, t).z]).sort((a, b) => a[1] - b[1]).map(a => a[0]);

  /* ---------- layers ---------- */
  function buildLayer(l, errs) {
    try { l.fn = new Function('ctx', 'W', 'H', 't', 'rand', l.code || ''); } catch (e) { l.fn = () => {}; errs.push(`layer ${l.name} does not compile: ${e.message}`); return; }
    if (l.animated) return;
    const pw = (W + 2 * OVER) * PR, ph = H * PR, raw = mk(pw, ph), c = raw.getContext('2d');
    c.setTransform(PR, 0, 0, PR, OVER * PR, 0);
    try { l.fn(c, W, H, 0, seeded(l.name.length * 977 + 13)); } catch (e) { errs.push(`layer ${l.name} crashed: ${e.message}`); }
    const baked = mk(pw, ph), b = baked.getContext('2d');
    if (S.layers.indexOf(l) > 0 || l.front) { b.shadowColor = 'rgba(45,25,10,0.32)'; b.shadowBlur = 9 * PR; b.shadowOffsetY = 3 * PR; }
    b.drawImage(raw, 0, 0); l.img = baked;
  }
  function drawLayer(ctx, l, t, cam) {
    const shift = cam * (l.depth ?? 0.5);
    if (l.animated) {
      ctx.save(); ctx.translate(shift, 0);
      try { l.fn(ctx, W, H, t, seeded(l.name.length * 977 + 13)); } catch (e) { noteErr(`layer ${l.name}: ${e.message}`); }
      ctx.restore();
    } else if (l.img) ctx.drawImage(l.img, -OVER + shift, 0, W + 2 * OVER, H);
  }

  /* ---------- frame ---------- */
  let grain = null;
  function grainTex() {
    if (grain) return grain;
    grain = mk(256, 256); const c = grain.getContext('2d'), d = c.createImageData(256, 256), r = seeded(7);
    for (let i = 0; i < d.data.length; i += 4) { const v = 118 + r() * 20; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
    c.putImageData(d, 0, 0); return grain;
  }
  const camAt = t => 7 * Math.sin(2 * Math.PI * t / (S.stage.duration || 12));
  let actorCv = null;
  function render(ctx, t, o = {}) {
    const { scale = PR, back = true, actors = true, front = true, fx = true } = o, cam = camAt(t);
    ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.clearRect(0, 0, W, H);
    if (back) for (const l of S.layers) if (!l.front) drawLayer(ctx, l, t, cam);
    if (actors) for (const id of actorsByZ(t)) {
      const s = actorState(id, t);
      if (s.opacity > 0.05 && !s.clip) {
        const sh = clamp(1 - s.arc / 120 - s.lift / 200, 0.25, 1) * s.opacity;
        ctx.save(); ctx.fillStyle = `rgba(35,20,10,${0.26 * sh})`; ctx.beginPath(); ctx.ellipse(s.x + cam * 0.7, s.baseY + 3, 46 * s.scale * sh, 9 * s.scale, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      }
      if (fx) {
        actorCv = actorCv || mk(W * PR, H * PR); const a = actorCv.getContext('2d');
        a.setTransform(PR, 0, 0, PR, 0, 0); a.clearRect(0, 0, W, H); drawActor(a, id, t, cam * 0.7);
        ctx.save(); ctx.shadowColor = 'rgba(40,22,8,0.34)'; ctx.shadowBlur = 5 * scale; ctx.shadowOffsetY = 2 * scale; ctx.drawImage(actorCv, 0, 0, W, H); ctx.restore();
      } else drawActor(ctx, id, t, cam * 0.7);
    }
    if (front) for (const l of S.layers) if (l.front) drawLayer(ctx, l, t, cam);
    if (fx) { ctx.save(); ctx.globalAlpha = 0.16; ctx.globalCompositeOperation = 'overlay'; ctx.fillStyle = ctx.createPattern(grainTex(), 'repeat'); ctx.fillRect(0, 0, W, H); ctx.restore(); }
  }

  /* ---------- eyes for a text-only model ---------- */
  const NAMES = [['k', 22, 20, 20], ['w', 242, 238, 228], ['a', 135, 130, 125], ['r', 185, 55, 45], ['o', 222, 135, 55], ['y', 236, 205, 95], ['l', 150, 185, 95], ['g', 85, 135, 70], ['d', 42, 75, 52], ['b', 70, 110, 185], ['s', 165, 200, 225], ['p', 236, 165, 182], ['n', 110, 70, 45], ['t', 216, 182, 138]];
  function letter(r, g, b) { let best = '?', bd = 1e9; for (const [n, a, c, e] of NAMES) { const d = (r - a) ** 2 + (g - c) ** 2 + (b - e) ** 2; if (d < bd) { bd = d; best = n; } } return best; }
  const mctx = () => (mctx.c = mctx.c || mk(W, H).getContext('2d', { willReadFrequently: true }));
  const fctx = () => (fctx.c = fctx.c || mk(FW, FH).getContext('2d', { willReadFrequently: true }));
  const fctx2 = () => (fctx2.c = fctx2.c || mk(FW, FH).getContext('2d', { willReadFrequently: true }));

  function actorMask(id, t) {
    const c = mctx(); c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, H);
    c.setTransform(R, 0, 0, R, OX, OY); const s = drawActor(c, id, t, camAt(t) * 0.7);
    const d = c.getImageData(0, 0, W, H).data, px = new Uint8Array(FW * FH);
    let total = 0, inF = 0, x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, sum = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4; if (d[i + 3] < 110) continue;
      total++; x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      const fx = x - OX, fy = y - OY;
      if (fx >= 0 && fy >= 0 && fx < FW && fy < FH) { inF++; px[fy * FW + fx] = 1; sum += lum(d[i], d[i + 1], d[i + 2]); }
    }
    return { s, total, inF, px, meanL: inF ? sum / inF : 0, bbox: total ? [(x0 - OX) / R, (y0 - OY) / R, (x1 - OX) / R, (y1 - OY) / R].map(Math.round) : null };
  }
  function renderSmall(ctx, t, o) { render(ctx, t, { ...o, scale: R, fx: false }); return ctx.getImageData(0, 0, FW, FH).data; }

  function asciiFrame(t) {
    const c = fctx2(), d = renderSmall(c, t, {}), cols = 39, rows = 26, cw = FW / cols, ch = FH / rows;
    const ids = actorsByZ(t).map(id => actorMask(id, t).px), out = [];
    for (let r = 0; r < rows; r++) {
      let line = '';
      for (let q = 0; q < cols; q++) {
        let a = 0, b = 0, e = 0, n = 0, on = 0;
        for (let y = Math.floor(r * ch); y < Math.floor((r + 1) * ch); y++) for (let x = Math.floor(q * cw); x < Math.floor((q + 1) * cw); x++) {
          const i = (y * FW + x) * 4; a += d[i]; b += d[i + 1]; e += d[i + 2]; n++;
          if (ids.some(m => m[y * FW + x])) on++;
        }
        const l = letter(a / n, b / n, e / n); line += on / n > 0.35 ? l.toUpperCase() : l;
      }
      out.push(line);
    }
    return out.join('\n');
  }
  function asciiPose(c, name) {
    const ctx = mk(200, 280).getContext('2d', { willReadFrequently: true });
    ctx.translate(100, 262); drawChar(ctx, c, poseOf(c, name), { blink: 0, mouth: 'smile', look: 0, brow: 0, t: 0 });
    const d = ctx.getImageData(0, 0, 200, 280).data, out = [];
    for (let r = 0; r < 28; r++) { let line = ''; for (let q = 0; q < 40; q++) { const x = q * 5 + 2, y = r * 10 + 5, i = (y * 200 + x) * 4; line += d[i + 3] < 110 ? '.' : letter(d[i], d[i + 1], d[i + 2]); } out.push(line.replace(/\.+$/, '')); }
    return out.join('\n').replace(/\n+$/, '');
  }
  function chamfer(mask, w, h) {
    const D = new Float32Array(w * h).fill(1e6);
    for (let i = 0; i < w * h; i++) if (mask[i]) D[i] = 0;
    const r2 = Math.SQRT2;
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) { const i = y * w + x; D[i] = Math.min(D[i], D[i - 1] + 1, D[i - w] + 1, D[i - w - 1] + r2, D[i - w + 1] + r2); }
    for (let y = h - 2; y > 0; y--) for (let x = w - 2; x > 0; x--) { const i = y * w + x; D[i] = Math.min(D[i], D[i + 1] + 1, D[i + w] + 1, D[i + w + 1] + r2, D[i + w - 1] + r2); }
    return D;
  }
  function jointGaps(c, name) {
    const w = 320, h = 360, ctx = mk(w, h).getContext('2d', { willReadFrequently: true }), ang = poseOf(c, name), found = [];
    const mask = bone => { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, w, h); ctx.setTransform(1, 0, 0, 1, 160, 330); drawChar(ctx, c, ang, { blink: 0, mouth: 'smile', look: 0, brow: 0, t: 0 }, [bone]); const d = ctx.getImageData(0, 0, w, h).data, m = new Uint8Array(w * h); let n = 0; for (let i = 0; i < w * h; i++) if (d[i * 4 + 3] > 110) { m[i] = 1; n++; } return { m, n }; };
    const cache = {}, get = b => (cache[b] = cache[b] || mask(b));
    for (const b of c.bones) {
      if (!b.parent) continue;
      const self = get(b.name), par = get(b.parent);
      if (!self.n) { found.push({ bone: b.name, problem: 'draws nothing' }); continue; }
      if (!par.n) continue;
      const D = chamfer(par.m, w, h); let min = 1e9; for (let i = 0; i < w * h; i++) if (self.m[i] && D[i] < min) min = D[i];
      if (min > 2) found.push({ bone: b.name, parent: b.parent, gap_px: Math.round(min), problem: 'detached from parent in this pose' });
    }
    return found;
  }
  function poseBounds(c, name) {
    const ctx = mk(400, 440).getContext('2d', { willReadFrequently: true }); ctx.translate(200, 400);
    drawChar(ctx, c, poseOf(c, name), { blink: 0, mouth: 'smile', look: 0, brow: 0, t: 0 });
    const d = ctx.getImageData(0, 0, 400, 440).data; let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let y = 0; y < 440; y++) for (let x = 0; x < 400; x++) if (d[(y * 400 + x) * 4 + 3] > 110) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    return x1 < 0 ? null : { left: x0 - 200, right: x1 - 200, top: y0 - 400, bottom: y1 - 400 };
  }

  function bgStats(t) {
    const d = renderSmall(fctx(), t, { actors: false, front: true }), hist = {}; let n = 0;
    for (let i = 0; i < d.length; i += 16) { const k = (d[i] >> 5) + ',' + (d[i + 1] >> 5) + ',' + (d[i + 2] >> 5); hist[k] = (hist[k] || 0) + 1; n++; }
    const top = Object.values(hist).sort((a, b) => b - a);
    const bands = []; const L = (x, y) => { const i = (y * FW + x) * 4; return lum(d[i], d[i + 1], d[i + 2]); };
    for (let b = 0; b < 6; b++) { let e = 0, c = 0; for (let y = Math.floor(b * FH / 6); y < Math.min(FH - 1, Math.floor((b + 1) * FH / 6)); y++) for (let x = 0; x < FW - 1; x++) { c++; if (Math.abs(L(x, y) - L(x + 1, y)) + Math.abs(L(x, y) - L(x, y + 1)) > 12) e++; } bands.push(Math.round(1000 * e / c) / 10); }
    return { largest_flat_colour_pct: Math.round(100 * top[0] / n), distinct_colour_buckets: top.length, edge_detail_pct_top_to_bottom: bands };
  }

  /* ---------- tools ---------- */
  function toolDefine(a) {
    runtimeErrors = [];
    const prior = S.chars[a.id]; let c;
    if (prior) { c = prior; for (const b of (a.bones || [])) { const i = c.bones.findIndex(x => x.name === b.name); if (i >= 0) c.bones[i] = { ...c.bones[i], ...b }; else c.bones.push(b); } Object.assign(c.poses, a.poses || {}); }
    else c = S.chars[a.id] = { id: a.id, bones: a.bones || [], poses: a.poses || {} };
    const errors = buildChar(c);
    if (errors.length) return { ok: false, errors };
    const poses = {}, names = Object.keys(c.poses); if (!names.includes('rest')) { c.poses.rest = {}; names.unshift('rest'); }
    const grounded = {}; for (const n of names) { if (/fly|flutter|air|leap|jump/i.test(n)) continue; const bb = poseBounds(c, n); if (bb && Math.abs(bb.bottom) > 2) { c.poses[n]._y = (c.poses[n]._y || 0) - bb.bottom; grounded[n] = -bb.bottom; } }
    for (const n of names) { const unknown = Object.keys(c.poses[n]).filter(k => k[0] !== '_' && !c.bones.some(b => b.name === k)); poses[n] = { bounds: poseBounds(c, n), joint_problems: jointGaps(c, n), unknown_bones: unknown.length ? unknown : undefined }; }
    return { ok: true, runtime_errors: runtimeErrors, bones: c.bones.length, poses, poses_auto_grounded_px: grounded, silhouette_rest: asciiPose(c, 'rest') };
  }
  function toolPaint(a) {
    runtimeErrors = []; const errors = [];
    if (a.ground) S.ground = a.ground; if (a.anchors) Object.assign(S.anchors, a.anchors);
    for (const l of (a.layers || [])) { const i = S.layers.findIndex(x => x.name === l.name); if (i >= 0) S.layers[i] = l; else S.layers.push(l); }
    for (const l of S.layers) buildLayer(l, errors);
    return { ok: !errors.length, errors, runtime_errors: runtimeErrors, layers: S.layers.map(l => l.name + (l.front ? ' (front)' : '') + (l.animated ? ' (animated)' : '')), stats: bgStats(0), frame: asciiFrame(0) };
  }
  function toolStage(a) {
    const errors = [];
    S.stage = { duration: a.duration || 12, start: a.start || {}, beats: a.beats || [] };
    for (const id of Object.keys(S.stage.start)) { const c = charOf(id); if (!c) { errors.push(`unknown character for actor ${id}`); continue; } const p = S.stage.start[id].pose; if (p && !c.poses[p]) errors.push(`${id} has no pose ${p}`); }
    for (const b of S.stage.beats) {
      const c = S.stage.start[b.actor] ? charOf(b.actor) : null; if (!c) { errors.push(`beat at ${b.at}: actor ${b.actor} is not in start`); continue; }
      for (const p of [b.pose, ...(b.cycle || [])]) if (p && !c.poses[p]) errors.push(`beat at ${b.at}: ${b.actor} has no pose ${p}`);
      if (b.clip && !S.anchors[b.clip]) errors.push(`beat at ${b.at}: no anchor ${b.clip}`);
    }
    return { ok: !errors.length, errors, beats: S.stage.beats.length, duration: S.stage.duration };
  }
  function toolCheck(a = {}) {
    runtimeErrors = [];
    const dur = S.stage.duration, ids = Object.keys(S.stage.start).filter(i => charOf(i)), issues = [], samples = [], add = (sev, what, at) => { const key = what.replace(/\d+/g, '#'), e = issues.find(i => i.key === key); if (e) { e.times.push(at); } else issues.push({ key, severity: sev, what, times: [at] }); };
    let prev = null, still = 0, stillFrom = 0;
    for (let t = 0; t <= dur + 1e-6; t += 0.5) {
      const fr = renderSmall(fctx(), t, { actors: false, front: true }).slice(), full = renderSmall(fctx2(), t, {}).slice();
      const fm = fctx(); render(fm, t, { scale: R, back: false, actors: false, front: true, fx: false }); const fd = fm.getImageData(0, 0, FW, FH).data;
      const row = { t }, masks = {};
      for (const id of ids) {
        const m = actorMask(id, t), s = m.s; masks[id] = m;
        if (s.opacity < 0.3 || !m.total) { row[id] = 'hidden'; continue; }
        const inPct = Math.round(100 * m.inF / m.total); let hid = 0, bgSum = 0, bgN = 0;
        for (let i = 0; i < FW * FH; i++) if (m.px[i]) { if (fd[i * 4 + 3] > 128) hid++; else { bgSum += lum(fr[i * 4], fr[i * 4 + 1], fr[i * 4 + 2]); bgN++; } }
        const hidPct = m.inF ? Math.round(100 * hid / m.inF) : 0, h = Math.max(m.bbox[3] - m.bbox[1], m.bbox[2] - m.bbox[0]), small = /sparrow|mouse|swallow|bird|reed/.test(id + ' ' + (S.stage.start[id].char || ''));
        row[id] = { bbox: m.bbox, inframe: inPct, hidden_by_front: hidPct, x: Math.round(s.x) };
        if (!s.clip && !s.exiting) {
          if (inPct < 97) add('high', `${id} is ${100 - inPct}% outside the frame, bbox ${m.bbox}`, t);
          if (h < (small ? 60 : 130)) add('medium', `${id} is only ${h}px across, too small on a phone card`, t);
          if (hidPct > 35) add('high', `${id} is ${hidPct}% hidden by front layers`, t);
          if (s.lift === 0 && !s.arc && Math.abs(m.bbox[3] - s.baseY) > 16) add('high', `${id} feet at y=${m.bbox[3]} but ground is y=${Math.round(s.baseY)}, so it floats or sinks`, t);
        }
      }
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const A = masks[ids[i]], B = masks[ids[j]]; if (!A.inF || !B.inF) continue; const sm = id => /sparrow|mouse|swallow|bird/.test(id + ' ' + (S.stage.start[id].char || '')); if (sm(ids[i]) || sm(ids[j])) continue; let o = 0;
        for (let k = 0; k < FW * FH; k++) if (A.px[k] && B.px[k]) o++;
        const pct = Math.round(100 * o / Math.min(A.inF, B.inF)); if (pct > 30) add('medium', `${ids[i]} and ${ids[j]} overlap by ${pct}%`, t);
      }
      if (prev) { let diff = 0; for (let i = 0; i < full.length; i += 16) diff += Math.abs(full[i] - prev[i]) + Math.abs(full[i + 1] - prev[i + 1]); diff /= full.length / 16; if (diff < 0.7) { if (!still) stillFrom = t - 0.5; still += 0.5; } else { if (still >= 2.5) add('medium', `nothing visibly moves from ${stillFrom}s for ${still}s`, stillFrom); still = 0; } }
      prev = full; samples.push(row);
    }
    if (still >= 2.5) add('medium', `nothing visibly moves from ${stillFrom}s for ${still}s`, stillFrom);
    for (const c of new Set(ids.map(charOf))) for (const n of Object.keys(c.poses)) for (const g of jointGaps(c, n)) if (g.gap_px) add('high', `${c.id} pose ${n}: ${g.bone} ${g.problem} by ${g.gap_px}px`, 0);
    const bg = bgStats(0); if (bg.largest_flat_colour_pct > 30) add('medium', `${bg.largest_flat_colour_pct}% of the frame is one flat colour, so the world feels empty`, 0);
    bg.edge_detail_pct_top_to_bottom.forEach((v, i) => { if (v < 3) add('medium', `band ${i + 1} of 6 from the top (y ${Math.round(i * H / 6)} to ${Math.round((i + 1) * H / 6)}) is nearly empty, edge detail ${v}%: add shapes and depth there`, 0); });
    if (S.layers.filter(l => !l.animated).length < 5) add('medium', `only ${S.layers.filter(l => !l.animated).length} static layers, use at least 5`, 0);
    for (const e of runtimeErrors) add('high', 'runtime error: ' + e, 0);
    const times = (a.times && a.times.length ? a.times : [dur * 0.15, dur * 0.5, dur * 0.8]).slice(0, 3);
    const frames = {}; for (const t of times) frames[`t=${(+t).toFixed(1)}`] = asciiFrame(+t);
    return { issue_count: issues.length, issues: issues.map(({ severity, what, times }) => ({ severity, what, times: times.slice(0, 6) })), background: bg, samples: samples.filter((_, i) => i % 2 === 0), frames };
  }

  const exportScene = () => JSON.parse(JSON.stringify({
    chars: Object.fromEntries(Object.entries(S.chars).map(([k, c]) => [k, { id: c.id, poses: c.poses, bones: c.bones.map(({ name, parent, pivot, rest, z, code }) => ({ name, parent, pivot, rest, z, code })) }])),
    layers: S.layers.map(({ name, depth, front, animated, code }) => ({ name, depth, front, animated, code })),
    ground: S.ground, anchors: S.anchors, stage: S.stage,
  }));
  function load(sc) {
    S.chars = sc.chars; S.ground = sc.ground; S.anchors = sc.anchors; S.stage = sc.stage; S.layers = sc.layers;
    for (const c of Object.values(S.chars)) buildChar(c);
    const e = []; for (const l of S.layers) buildLayer(l, e); return e;
  }
  const renderActor = (ctx, id, t, scale) => { ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.clearRect(0, 0, W, H); drawActor(ctx, id, t, 0); };
  const actorIds = () => Object.keys(S.stage.start).filter(id => charOf(id));
  const actorInfo = (id, t) => { const s = actorState(id, t); return { z: s.z, opacity: s.opacity, plane: (S.stage.start[id] || {}).plane }; };
  const reset = (keepChars) => { if (!keepChars) S.chars = {}; S.layers = []; S.anchors = {}; S.ground = [[-30, 440], [420, 440]]; S.stage = { duration: 12, start: {}, beats: [] }; };
  const addChars = list => { const out = []; for (const c of list) { S.chars[c.id] = c; out.push(...buildChar(c)); } return out; };
  const poseSheet = (ctx, id, pose, face) => { const c = S.chars[id]; ctx.save(); drawChar(ctx, c, poseOf(c, pose), { blink: 0, mouth: 'smile', look: 0, brow: 0, t: 0, ...(face || {}) }); ctx.restore(); };
  const drawAnimated = (ctx, t, scale) => { ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.clearRect(0, 0, W, H); for (const l of S.layers) if (l.animated) drawLayer(ctx, l, t, 0); };
  root.LB = { W, H, PR, OVER, layers: () => S.layers, drawAnimated, renderActor, actorIds, actorInfo, reset, addChars, poseSheet, render, toolDefine, toolPaint, toolStage, toolCheck, exportScene, load, duration: () => S.stage.duration, errors: () => runtimeErrors };
})(window);
