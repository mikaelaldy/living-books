// Pop-up stage: Beam's paper sheets stand at real depths; actors share one sheet so phones stay smooth.
import * as THREE from 'three';

const W = 390, H = 520, U = 0.01, D = 9, ACTOR_SCALE = 1.25;

export class PopupStage {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.setSize(canvas.clientWidth || W, canvas.clientHeight || H, false);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#efdcc4');
    this.cam = new THREE.PerspectiveCamera((2 * Math.atan((H * U) / 2 / D) * 180) / Math.PI, W / H, 0.1, 60);
    this.cam.position.set(0, 0, D);
    this.scene.add(new THREE.HemisphereLight('#fff6ea', '#d3b79c', 2.75));
    const sun = new THREE.DirectionalLight('#ffe7c4', 0.95);
    sun.position.set(-3.5, 4.5, 7); sun.castShadow = true; sun.shadow.mapSize.set(768, 768);
    Object.assign(sun.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5, near: 1, far: 24 });
    sun.shadow.bias = -0.0006; sun.shadow.radius = 5; sun.shadow.autoUpdate = false; this.sun = sun; this.tick = 0;
    this.scene.add(sun);
    this.group = new THREE.Group(); this.scene.add(this.group);
  }

  resize() { this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight, false); }

  plane(tex, z, wpx, order, opts = {}) {
    const k = (D - z) / D, g = new THREE.PlaneGeometry(wpx * U * k, H * U * k);
    tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 2; tex.generateMipmaps = false; tex.minFilter = THREE.LinearFilter;
    const m = new THREE.MeshLambertMaterial({ map: tex, transparent: true, alphaTest: 0.45, side: THREE.DoubleSide });
    const p = new THREE.Mesh(g, m); p.position.z = z; p.renderOrder = order;
    p.castShadow = opts.cast !== false; p.receiveShadow = opts.receive !== false; this.group.add(p); return p;
  }

  clear() {
    for (const o of [...this.group.children]) { this.group.remove(o); o.geometry.dispose(); o.material.map?.dispose(); o.material.dispose(); }
  }

  // Call after LB.load(scene).
  load() {
    this.clear();
    const all = LB.layers(), back = all.filter(l => !l.front && !l.animated), front = all.filter(l => l.front && !l.animated);
    const ds = back.map(l => l.depth ?? 0.5), lo = Math.min(...ds), hi = Math.max(...ds), span = Math.max(0.001, hi - lo);
    back.forEach((l, i) => {
      const n = ((l.depth ?? 0.5) - lo) / span, z = -5.2 * (1 - n) ** 1.25 - 0.35 - 0.001 * (back.length - i);
      const p = this.plane(new THREE.CanvasTexture(l.img), z, W + 2 * LB.OVER, i, { cast: i > 0 });
      if (i === 0) p.scale.set(1.3, 1.3, 1);
    });
    const ac = document.createElement('canvas'); ac.width = W * ACTOR_SCALE; ac.height = H * ACTOR_SCALE;
    this.sheet = { ctx: ac.getContext('2d'), tex: new THREE.CanvasTexture(ac) };
    this.plane(this.sheet.tex, 0, W, 20);
    front.forEach((l, i) => this.plane(new THREE.CanvasTexture(l.img), 1.15 + i * 0.35, W + 2 * LB.OVER, 40 + i));
    this.fx = null;
    if (all.some(l => l.animated)) {
      const c = document.createElement('canvas'); c.width = W; c.height = H;
      this.fx = { ctx: c.getContext('2d'), tex: new THREE.CanvasTexture(c) };
      this.plane(this.fx.tex, 0.8, W, 35, { cast: false, receive: false });
    }
  }

  show(t, cx = 0, cy = 0) {
    LB.render(this.sheet.ctx, t, { scale: ACTOR_SCALE, back: false, front: false, fx: false });
    this.sheet.tex.needsUpdate = true;
    if (this.fx && this.tick % 2 === 0) { LB.drawAnimated(this.fx.ctx, t, 1); this.fx.tex.needsUpdate = true; }
    if (this.tick++ % 4 === 0) this.sun.shadow.needsUpdate = true;
    this.cam.position.set(cx, cy, D); this.cam.lookAt(0, 0, -1);
    this.renderer.render(this.scene, this.cam);
  }

  dispose() { this.clear(); this.renderer.dispose(); this.renderer.forceContextLoss?.(); }
}
