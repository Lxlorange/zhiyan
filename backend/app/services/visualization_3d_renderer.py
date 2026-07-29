from __future__ import annotations

import html
import json
from typing import Any


def render_three_physics_html(demo: dict[str, Any], page_title: str) -> str:
    data_json = json.dumps(demo, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(page_title)
    return THREE_PHYSICS_TEMPLATE.replace("__PAGE_TITLE__", safe_title).replace("__DEMO_JSON__", data_json)


THREE_PHYSICS_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__PAGE_TITLE__</title>
  <style>
    :root {
      color: #e2e8f0;
      background: #0b1120;
      font-family: Inter, "Microsoft YaHei", system-ui, sans-serif;
      --accent: #38bdf8;
      --accent2: #34d399;
      --surface: rgba(15, 23, 42, 0.88);
      --border: rgba(56, 189, 248, 0.18);
      --text: #e2e8f0;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      overflow: hidden;
      background: radial-gradient(ellipse at 50% 30%, #1e293b 0%, #0b1120 60%, #020617 100%);
    }
    .app {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      height: 100vh;
      gap: 0;
    }
    .stage {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      position: relative;
      overflow: hidden;
    }
    .canvas-wrap {
      position: relative;
      min-height: 0;
      overflow: hidden;
      cursor: grab;
    }
    .canvas-wrap:active { cursor: grabbing; }
    .canvas-wrap.pointer { cursor: pointer; }
    #scene {
      width: 100%;
      height: 100%;
      display: block;
    }

    /* ---------- HUD ---------- */
    .hud {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      padding: 10px 12px;
      pointer-events: none;
    }
    .hud > * { pointer-events: auto; }
    .title-card {
      min-width: 0;
      border-radius: 14px;
      padding: 10px 14px;
      background: var(--surface);
      border: 1px solid var(--border);
      backdrop-filter: blur(20px);
    }
    .title-card .eyebrow {
      display: flex; gap: 8px; align-items: center;
      color: var(--accent); font-size: 11px; font-weight: 800;
      letter-spacing: 0.04em; text-transform: uppercase;
    }
    .title-card h1 {
      margin-top: 4px; color: #f1f5f9; font-size: 18px; line-height: 1.25;
    }
    .title-card p {
      margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.4;
      display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2;
    }
    .status-card {
      min-width: 170px; border-radius: 14px; padding: 10px 14px;
      background: var(--surface); border: 1px solid var(--border);
      backdrop-filter: blur(20px); text-align: right;
    }
    .status-card strong { display: block; color: #f1f5f9; font-size: 15px; }
    .status-card small {
      display: block; color: var(--muted); margin-top: 4px; line-height: 1.4;
      display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 3;
    }

    /* ---------- Timeline controls ---------- */
    .timeline {
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr) auto auto;
      gap: 8px;
      align-items: center;
      margin: 8px 12px 10px;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 8px 12px;
      background: var(--surface);
      backdrop-filter: blur(20px);
    }
    button {
      height: 34px; padding: 0 13px;
      border: 1px solid var(--accent); border-radius: 10px;
      background: var(--accent); color: #0b1120;
      font-weight: 800; font-size: 12px; cursor: pointer;
      white-space: nowrap;
      transition: all 0.18s ease;
    }
    button:hover { filter: brightness(1.15); }
    button.secondary { background: transparent; color: var(--accent); }
    button.secondary:hover { background: rgba(56,189,248,0.12); }
    .step-btns { display: flex; gap: 4px; overflow-x: auto; padding: 2px 0; }
    .step-btns button {
      min-width: 34px; height: 28px; padding: 0 8px;
      font-size: 11px; font-weight: 700;
      border-color: rgba(148,163,184,0.25);
      background: transparent; color: var(--muted);
    }
    .step-btns button.active {
      border-color: var(--accent); background: rgba(56,189,248,0.15); color: var(--accent);
    }
    .bar {
      height: 8px; overflow: hidden; border-radius: 999px;
      background: rgba(148,163,184,0.15);
    }
    .bar i {
      display: block; width: 0%; height: 100%; border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      transition: width 280ms ease;
    }

    /* ---------- Side panel ---------- */
    .side {
      overflow-y: auto; overflow-x: hidden;
      border-left: 1px solid var(--border);
      background: rgba(15,23,42,0.72);
      backdrop-filter: blur(20px);
      padding: 12px;
      display: grid; align-content: start; gap: 10px;
    }
    .panel {
      display: grid; gap: 8px;
      border-radius: 14px; padding: 12px;
      background: rgba(30,41,59,0.7);
      border: 1px solid rgba(56,189,248,0.1);
    }
    .panel strong { color: #f1f5f9; font-size: 13px; font-weight: 800; }
    .panel p, .panel li, .panel label { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .panel ul { margin: 0; padding-left: 16px; display: grid; gap: 4px; }
    .object-list { display: grid; gap: 6px; }
    .object-row {
      display: grid; grid-template-columns: 12px minmax(0, 1fr) auto;
      gap: 8px; align-items: center; color: #cbd5e1; font-size: 12px;
      padding: 6px 8px; border-radius: 8px; cursor: pointer;
      transition: background 0.16s ease;
    }
    .object-row:hover { background: rgba(56,189,248,0.1); }
    .object-row.selected { background: rgba(56,189,248,0.18); border: 1px solid rgba(56,189,248,0.3); }
    .swatch {
      width: 12px; height: 12px; border-radius: 999px;
      background: var(--color); box-shadow: 0 0 8px var(--color);
    }
    .slider-row { display: grid; gap: 4px; }
    .slider-row .head { display: flex; justify-content: space-between; color: #cbd5e1; font-size: 12px; }
    input[type="range"] { width: 100%; accent-color: var(--accent); }

    /* ---------- Inspect popup ---------- */
    .inspect-popup {
      position: absolute; left: 16px; bottom: 16px;
      display: none; width: min(320px, calc(100% - 32px));
      gap: 6px; padding: 12px;
      border: 1px solid var(--accent); border-radius: 14px;
      background: rgba(15,23,42,0.94);
      backdrop-filter: blur(20px);
      box-shadow: 0 20px 50px rgba(0,0,0,0.5);
      z-index: 10;
    }
    .inspect-popup.open { display: grid; }
    .inspect-popup .close-btn {
      position: absolute; top: 6px; right: 8px;
      background: none; border: none; color: var(--muted);
      font-size: 16px; cursor: pointer; padding: 2px 6px;
    }
    .inspect-popup strong { color: #f1f5f9; font-size: 14px; }
    .inspect-popup span { color: var(--accent); font-size: 11px; font-weight: 800; }
    .inspect-popup p { color: var(--muted); font-size: 12px; line-height: 1.5; }

    /* ---------- Responsive ---------- */
    @media (max-width: 960px) {
      body { overflow: auto; }
      .app { grid-template-columns: 1fr; height: auto; min-height: 100vh; }
      .stage { min-height: 75vh; }
      .hud { grid-template-columns: 1fr; }
      .status-card { text-align: left; }
      .side { border-left: none; border-top: 1px solid var(--border); }
    }
  </style>
  <script type="importmap">
    {
      "imports": {
        "three": "https://esm.sh/three@0.167.1",
        "three/addons/": "https://esm.sh/three@0.167.1/examples/jsm/"
      }
    }
  </script>
</head>
<body>
  <div class="app">
    <main class="stage">
      <section class="hud">
        <div class="title-card">
          <div class="eyebrow">
            <span id="kind">3D Physics</span>
            <span id="sceneKind"></span>
          </div>
          <h1 id="title">__PAGE_TITLE__</h1>
          <p id="description"></p>
        </div>
        <div class="status-card">
          <strong id="frameLabel"></strong>
          <small id="frameNarrative"></small>
        </div>
      </section>
      <div class="canvas-wrap" id="canvasWrap">
        <canvas id="scene"></canvas>
        <div class="inspect-popup" id="inspectPopup">
          <button class="close-btn" id="closeInspect">&times;</button>
          <span id="inspectKind"></span>
          <strong id="inspectLabel"></strong>
          <p id="inspectDetail"></p>
        </div>
      </div>
      <section class="timeline">
        <button id="prevBtn" class="secondary" title="上一步">&larr;</button>
        <button id="play">播放</button>
        <div class="bar"><i id="progress"></i></div>
        <div class="step-btns" id="stepBtns"></div>
        <button id="reset" class="secondary">重置</button>
      </section>
    </main>
    <aside class="side">
      <section class="panel">
        <strong>学习目标</strong>
        <p id="goal"></p>
      </section>
      <section class="panel">
        <strong>场景对象（点击查看详情）</strong>
        <div class="object-list" id="objectList"></div>
      </section>
      <section class="panel">
        <strong>操控面板</strong>
        <div id="controls"></div>
      </section>
      <section class="panel">
        <strong>讲解要点</strong>
        <ul id="points"></ul>
      </section>
      <section class="panel">
        <strong>学习任务</strong>
        <ul id="tasks"></ul>
      </section>
    </aside>
  </div>
  <script id="demo-data" type="application/json">__DEMO_JSON__</script>
  <script type="module">
    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
    import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
    import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

    // ── Parse demo data ──────────────────────────────────
    const demo = JSON.parse(document.getElementById('demo-data').textContent);
    const sceneSpec = demo.physics_scene;
    if (!sceneSpec || !Array.isArray(sceneSpec.objects) || !sceneSpec.objects.length) {
      document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;color:#f1f5f9;font-size:18px;">缺少 physics_scene.objects，无法渲染 3D 物理演示。<br>请在互动面板中重新生成。</div>';
      throw new Error('Missing physics_scene.objects');
    }

    const canvas = document.getElementById('scene');
    const canvasWrap = document.getElementById('canvasWrap');

    // ── Renderer ─────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    // ── Scene ────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1120);
    scene.fog = new THREE.FogExp2(0x0b1120, 0.00025);

    // ── Camera ───────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 180);
    const cameraConfig = sceneSpec.camera || {};
    const defaultCamPos = [9, 6, 13];
    camera.position.set(...vec3(cameraConfig.position, defaultCamPos));
    const defaultCamTarget = [0, 1.2, 0];
    const camTarget = new THREE.Vector3(...vec3(cameraConfig.target, defaultCamTarget));

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(camTarget);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 2.5;
    controls.maxDistance = 45;
    controls.maxPolarAngle = Math.PI * 0.78;
    controls.update();

    // ── Post-processing ──────────────────────────────────
    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      0.55,   // strength
      0.4,    // radius
      0.2     // threshold
    );
    composer.addPass(bloomPass);

    // ── Lighting ─────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0x1e3a5f, 1.8);
    scene.add(ambient);
    const hemi = new THREE.HemisphereLight(0x7eb8da, 0x1a2744, 1.2);
    scene.add(hemi);
    const keyLight = new THREE.DirectionalLight(0xf0f9ff, 3.5);
    keyLight.position.set(10, 16, 8);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 80;
    keyLight.shadow.camera.left = -20;
    keyLight.shadow.camera.right = 20;
    keyLight.shadow.camera.top = 20;
    keyLight.shadow.camera.bottom = -20;
    keyLight.shadow.bias = -0.0003;
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0x38bdf8, 1.6);
    rimLight.position.set(-4, 2, -4);
    scene.add(rimLight);

    // ── Physics world (no cannon-es — pure kinematic animation) ──
    // Using spring-based procedural animation for smoother visuals
    // and to avoid the heavy cannon-es dependency in the import map.

    // ── Floor & Grid ─────────────────────────────────────
    const floorGeo = new THREE.CircleGeometry(22, 64);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x111c2e, roughness: 0.55, metalness: 0.35
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.15;
    floor.receiveShadow = true;
    scene.add(floor);

    const gridHelper = new THREE.PolarGridHelper(20, 48, 32, 128, 0x1e3a5f, 0x1e3a5f);
    gridHelper.position.y = 0.01;
    scene.add(gridHelper);

    // ── Starfield particles ──────────────────────────────
    const starsGeo = new THREE.BufferGeometry();
    const starsCount = 600;
    const starsPositions = new Float32Array(starsCount * 3);
    for (let i = 0; i < starsCount; i++) {
      starsPositions[i * 3] = (Math.random() - 0.5) * 50;
      starsPositions[i * 3 + 1] = Math.random() * 18 + 1;
      starsPositions[i * 3 + 2] = (Math.random() - 0.5) * 50;
    }
    starsGeo.setAttribute('position', new THREE.BufferAttribute(starsPositions, 3));
    const starsMat = new THREE.PointsMaterial({
      color: 0x7eb8da, size: 0.04, transparent: true, opacity: 0.7,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const stars = new THREE.Points(starsGeo, starsMat);
    scene.add(stars);

    // ── Create sim objects ───────────────────────────────
    const simObjects = new Map();
    const particleEmitters = [];
    const highlightRings = [];
    const allMeshes = [];

    for (const spec of sceneSpec.objects) {
      const entry = createSimObject(spec);
      simObjects.set(spec.id, entry);
      scene.add(entry.group);
      allMeshes.push(entry.mesh);
      if (spec.particle_emitter || spec.role === 'source' || spec.role === 'emitter') {
        particleEmitters.push(createParticleEmitter(entry, spec));
      }
    }

    // ── Connection lines ─────────────────────────────────
    const connectionLines = [];
    createConnections();

    // ── Annotation arrows ────────────────────────────────
    const annotations = [];
    if (Array.isArray(sceneSpec.annotations)) {
      for (const ann of sceneSpec.annotations) {
        annotations.push(createAnnotation(ann));
      }
    }

    // ── Runtime state ────────────────────────────────────
    const clock = new THREE.Clock();
    const runtime = {
      playing: false,
      speed: 1,
      force: 1,
      damping: 0.04,
      frameIndex: -1,
      elapsed: 0,
      selectedId: null,
      cameraKeyframes: [],
      targetPosition: new THREE.Vector3(),
      targetLookAt: new THREE.Vector3(),
      animatingCamera: false,
      cameraAnimStart: 0,
      cameraAnimDuration: 0.9,
    };

    // Parse camera keyframes from frames if present
    if (Array.isArray(demo.frames)) {
      runtime.cameraKeyframes = demo.frames.map((f) => ({
        position: f.camera_position || null,
        target: f.camera_target || null,
      }));
    }

    // ── Build UI ─────────────────────────────────────────
    buildInfoPanel();
    buildStepButtons();
    buildControls();
    updateFrame(0);

    // ── Event listeners ──────────────────────────────────
    window.addEventListener('resize', resize);
    document.getElementById('play').onclick = togglePlay;
    document.getElementById('reset').onclick = resetSimulation;
    document.getElementById('prevBtn').onclick = () => {
      if (demo.frames && demo.frames.length > 1) {
        runtime.playing = false;
        updatePlayButton();
        updateFrame((runtime.frameIndex - 1 + demo.frames.length) % demo.frames.length);
      }
    };
    document.getElementById('closeInspect').onclick = closeInspect;

    // ── Raycaster for click interaction ──────────────────
    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 0.4;
    const mouse = new THREE.Vector2();
    canvas.addEventListener('click', onCanvasClick);
    canvas.addEventListener('mousemove', onCanvasMove);

    resize();
    animate();

    // ══════════════════════════════════════════════════════
    //  CREATE SIM OBJECT
    // ══════════════════════════════════════════════════════
    function createSimObject(spec) {
      const size = vec3(spec.size, [1.2, 1.2, 1.2]);
      const position = vec3(spec.position, [0, 2.5, 0]);
      const colorHex = spec.color || colorFromId(spec.id || spec.label || 'obj');
      const baseColor = new THREE.Color(colorHex);
      const emissiveColor = baseColor.clone().multiplyScalar(0.35);
      const shapeType = String(spec.shape || 'sphere').toLowerCase();

      const material = new THREE.MeshStandardMaterial({
        color: baseColor,
        roughness: 0.32,
        metalness: 0.22,
        emissive: emissiveColor,
        emissiveIntensity: 0.45,
      });

      let geometry;
      if (shapeType === 'box' || shapeType === 'cube' || shapeType === 'packet') {
        geometry = new THREE.BoxGeometry(size[0], size[1], size[2], 2, 2, 2);
      } else if (shapeType === 'cylinder' || shapeType === 'node') {
        geometry = new THREE.CylinderGeometry(size[0] / 2, size[0] / 2, size[1], 40);
      } else if (shapeType === 'torus') {
        geometry = new THREE.TorusGeometry(size[0] / 2, size[0] / 5, 24, 48);
      } else if (shapeType === 'plane') {
        geometry = new THREE.BoxGeometry(size[0], 0.12, size[2] || size[0], 1, 1, 1);
      } else {
        const radius = Math.max(0.25, size[0] / 2);
        geometry = new THREE.SphereGeometry(radius, 48, 36);
      }

      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData = {
        spec,
        initialPosition: [...position],
        velocity: vec3(spec.velocity, [0, 0, 0]),
        phase: Math.random() * Math.PI * 2,
        orbitRadius: 0,
        orbitSpeed: 0,
      };

      // Glow shell
      const glowGeo = geometry.clone();
      const glowMat = new THREE.MeshBasicMaterial({
        color: baseColor,
        transparent: true,
        opacity: 0.15,
        depthWrite: false,
      });
      const glowShell = new THREE.Mesh(glowGeo, glowMat);
      glowShell.scale.set(1.22, 1.22, 1.22);
      glowShell.userData = { isGlow: true };

      // Label sprite
      const labelSprite = createLabelSprite(spec.label || spec.id || 'Object', colorHex);
      labelSprite.position.set(0, Math.max(size[1], size[0]) * 0.75 + 0.5, 0);

      // Highlight ring (hidden by default)
      const ringGeo = new THREE.TorusGeometry(Math.max(size[0], size[1]) * 0.72, 0.06, 16, 48);
      const ringMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.visible = false;
      highlightRings.push({ ring, mesh, id: spec.id });

      const group = new THREE.Group();
      group.add(mesh);
      group.add(glowShell);
      group.add(labelSprite);
      group.add(ring);
      group.position.set(...position);
      group.userData = { id: spec.id, spec };

      return { spec, group, mesh, glowShell, label: labelSprite, ring, size, initialPosition: [...position] };
    }

    // ══════════════════════════════════════════════════════
    //  PARTICLE EMITTER
    // ══════════════════════════════════════════════════════
    function createParticleEmitter(entry, spec) {
      const maxParticles = 180;
      const positionsArr = new Float32Array(maxParticles * 3);
      const colorsArr = new Float32Array(maxParticles * 3);
      const sizesArr = new Float32Array(maxParticles);
      const baseColor = new THREE.Color(spec.color || colorFromId(spec.id || 'emit'));

      for (let i = 0; i < maxParticles; i++) {
        positionsArr[i * 3] = 0;
        positionsArr[i * 3 + 1] = -99;
        positionsArr[i * 3 + 2] = 0;
        colorsArr[i * 3] = baseColor.r;
        colorsArr[i * 3 + 1] = baseColor.g;
        colorsArr[i * 3 + 2] = baseColor.b;
        sizesArr[i] = Math.random() * 0.08 + 0.03;
      }

      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(positionsArr, 3));
      geo.setAttribute('color', new THREE.BufferAttribute(colorsArr, 3));
      geo.setAttribute('size', new THREE.BufferAttribute(sizesArr, 1));

      const mat = new THREE.PointsMaterial({
        size: 0.12,
        vertexColors: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        transparent: true,
        opacity: 0.75,
      });

      const points = new THREE.Points(geo, mat);
      scene.add(points);

      const velocities = [];
      for (let i = 0; i < maxParticles; i++) {
        velocities.push({
          vx: (Math.random() - 0.5) * 0.8,
          vy: Math.random() * 1.6 + 0.3,
          vz: (Math.random() - 0.5) * 0.8,
          life: Math.random() * 1.8 + 0.4,
          age: Math.random() * 2,
        });
      }

      return { points, geo, positionsArr, velocities, maxParticles, entry };
    }

    // ══════════════════════════════════════════════════════
    //  CONNECTIONS
    // ══════════════════════════════════════════════════════
    function createConnections() {
      const entries = Array.from(simObjects.values());
      if (entries.length < 2) return;
      for (let i = 1; i < entries.length; i++) {
        const a = entries[i - 1];
        const b = entries[i];
        const mid = new THREE.Vector3().addVectors(a.group.position, b.group.position).multiplyScalar(0.5);
        const curve = new THREE.QuadraticBezierCurve3(
          a.group.position.clone(),
          new THREE.Vector3(mid.x, mid.y + 1.2, mid.z),
          b.group.position.clone()
        );
        const tubeGeo = new THREE.TubeGeometry(curve, 48, 0.04, 8, false);
        const tubeMat = new THREE.MeshBasicMaterial({
          color: 0x38bdf8,
          transparent: true,
          opacity: 0.32,
          depthWrite: false,
        });
        const tube = new THREE.Mesh(tubeGeo, tubeMat);
        tube.userData = { a, b, curve };
        scene.add(tube);
        connectionLines.push(tube);

        // Flow dots along the connection
        const flowCount = 8;
        const flowGeo = new THREE.BufferGeometry();
        const flowPositionsArr = new Float32Array(flowCount * 3);
        flowGeo.setAttribute('position', new THREE.BufferAttribute(flowPositionsArr, 3));
        const flowMat = new THREE.PointsMaterial({
          size: 0.1,
          color: 0x7eb8da,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          transparent: true,
          opacity: 0.8,
        });
        const flowPoints = new THREE.Points(flowGeo, flowMat);
        flowPoints.userData = { curve, offsets: Array.from({ length: flowCount }, (_, j) => j / flowCount) };
        scene.add(flowPoints);
        connectionLines.push(flowPoints);
      }
    }

    // ══════════════════════════════════════════════════════
    //  ANNOTATION ARROW
    // ══════════════════════════════════════════════════════
    function createAnnotation(ann) {
      const origin = vec3(ann.origin, [0, 5, 0]);
      const dir = vec3(ann.direction, [0, -1, 0]);
      const length = Number(ann.length || 2);
      const color = new THREE.Color(ann.color || '#fbbf24');
      const arrow = new THREE.ArrowHelper(
        new THREE.Vector3(...dir).normalize(),
        new THREE.Vector3(...origin),
        length,
        color.getHex(),
        0.2,
        0.1
      );
      scene.add(arrow);
      return arrow;
    }

    // ══════════════════════════════════════════════════════
    //  LABEL SPRITE
    // ══════════════════════════════════════════════════════
    function createLabelSprite(text, colorHex) {
      const canvas2 = document.createElement('canvas');
      canvas2.width = 512;
      canvas2.height = 128;
      const ctx = canvas2.getContext('2d');
      ctx.clearRect(0, 0, 512, 128);
      ctx.fillStyle = 'rgba(11,17,32,0.82)';
      roundRectPath(ctx, 12, 16, 488, 82, 30);
      ctx.fill();
      ctx.strokeStyle = colorHex;
      ctx.lineWidth = 4;
      ctx.stroke();
      ctx.fillStyle = '#f1f5f9';
      ctx.font = '700 34px "Microsoft YaHei", Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(text).slice(0, 18), 256, 58);
      const tex = new THREE.CanvasTexture(canvas2);
      tex.minFilter = THREE.LinearFilter;
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false });
      const sprite = new THREE.Sprite(mat);
      sprite.scale.set(2.2, 0.55, 1);
      return sprite;
    }

    function roundRectPath(ctx, x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }

    // ══════════════════════════════════════════════════════
    //  ANIMATION LOOP
    // ══════════════════════════════════════════════════════
    function animate() {
      requestAnimationFrame(animate);
      const dt = Math.min(0.05, clock.getDelta()) * runtime.speed;
      const t = runtime.elapsed;

      if (runtime.playing) {
        runtime.elapsed += dt;
        const frameDuration = 2.5;
        const nextFrame = Math.floor(runtime.elapsed / frameDuration) % Math.max(1, (demo.frames || []).length);
        if (nextFrame !== runtime.frameIndex) updateFrame(nextFrame);
      }

      // Animate objects with procedural physics
      updateObjectAnimation(t, dt);

      // Update particles
      updateParticles(dt);

      // Update connection lines
      updateConnections();

      // Update starfield
      stars.rotation.y += dt * 0.03;
      stars.rotation.x += dt * 0.012;

      // Camera animation
      if (runtime.animatingCamera) {
        const elapsed = t - runtime.cameraAnimStart;
        const progress = Math.min(1, elapsed / runtime.cameraAnimDuration);
        const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
        camera.position.lerpVectors(
          camera.position.clone(),
          runtime.targetPosition,
          ease * 0.12 + 0.02
        );
        controls.target.lerp(runtime.targetLookAt, ease * 0.1 + 0.02);
        if (progress >= 1) runtime.animatingCamera = false;
      }

      controls.update();

      // Render with post-processing
      composer.render();
    }

    function updateObjectAnimation(t, dt) {
      const demoType = String(demo.demo_type || sceneSpec.scene_kind || '').toLowerCase();
      for (const [id, entry] of simObjects.entries()) {
        const pos = entry.group.position;
        const initial = entry.initialPosition;
        const phase = entry.mesh.userData.phase;
        const idx = Array.from(simObjects.keys()).indexOf(id);

        if (demoType.includes('signal') || demoType.includes('wave')) {
          pos.x = initial[0] + Math.sin(t * 2.0 + phase) * 2.5;
          pos.y = initial[1] + Math.cos(t * 1.6 + phase) * 1.6;
          pos.z = initial[2] + Math.cos(t * 2.2 + phase) * 2.0;
        } else if (demoType.includes('network') || demoType.includes('packet') || demoType.includes('graph')) {
          const targetX = (idx - (simObjects.size - 1) / 2) * 2.8;
          const targetZ = Math.sin(t * 1.2 + phase) * 3;
          pos.x += (targetX - pos.x) * 3.5 * dt;
          pos.z += (targetZ - pos.z) * 3.5 * dt;
          pos.y = initial[1] + Math.sin(t * 0.9 + phase) * 0.8;
        } else if (demoType.includes('neural') || demoType.includes('activation')) {
          pos.y = initial[1] + Math.max(0, Math.sin(t * 1.8 + phase)) * 2.2;
          pos.x = initial[0] + Math.cos(t * 1.1 + phase) * 0.6;
          pos.z = initial[2] + Math.sin(t * 0.9 + phase) * 0.6;
        } else if (demoType.includes('optimization') || demoType.includes('landscape')) {
          const r = 3 + idx * 1.2;
          const angle = t * 0.7 + idx * 1.3;
          pos.x = Math.cos(angle) * r;
          pos.z = Math.sin(angle) * r;
          pos.y = initial[1] + Math.sin(t * 0.6 + idx) * r * 0.4;
        } else if (demoType.includes('sorting') || demoType.includes('collision')) {
          const spacing = 2.2;
          pos.x = initial[0] + Math.sin(t * 1.4 + idx * 0.9) * 3.5;
          pos.z = initial[2] + Math.cos(t * 1.1 + idx * 0.7) * 2.5;
          pos.y = initial[1] + Math.abs(Math.sin(t * 2.0 + idx)) * 0.7;
        } else {
          // general_physics or default: gentle orbital motion
          pos.x = initial[0] + Math.sin(t * 0.7 + phase) * 2.0;
          pos.y = initial[1] + Math.cos(t * 0.55 + phase) * 1.2;
          pos.z = initial[2] + Math.cos(t * 0.65 + phase) * 2.0;
        }

        // Glow shell follows
        entry.glowShell.rotation.y += dt * 0.5;
        entry.glowShell.rotation.x += dt * 0.3;
        entry.glowShell.material.opacity = 0.12 + Math.sin(t * 3 + phase) * 0.05;

        // Ring animation for selected
        if (runtime.selectedId === id) {
          entry.ring.visible = true;
          entry.ring.material.opacity = 0.5 + Math.sin(t * 4) * 0.3;
          entry.ring.rotation.z += dt * 1.5;
        } else if (entry.ring.material.opacity > 0.02) {
          entry.ring.material.opacity *= 0.9;
          if (entry.ring.material.opacity < 0.03) entry.ring.visible = false;
        }
      }
    }

    function updateParticles(dt) {
      for (const emitter of particleEmitters) {
        const { points, geo, positionsArr, velocities, maxParticles, entry } = emitter;
        const src = entry.group.position;
        for (let i = 0; i < maxParticles; i++) {
          const v = velocities[i];
          v.age += dt;
          if (v.age >= v.life) {
            v.age = 0;
            v.life = Math.random() * 1.8 + 0.5;
            positionsArr[i * 3] = src.x + (Math.random() - 0.5) * 0.3;
            positionsArr[i * 3 + 1] = src.y + (Math.random() - 0.5) * 0.3;
            positionsArr[i * 3 + 2] = src.z + (Math.random() - 0.5) * 0.3;
            v.vx = (Math.random() - 0.5) * 0.9;
            v.vy = Math.random() * 1.8 + 0.4;
            v.vz = (Math.random() - 0.5) * 0.9;
          } else {
            positionsArr[i * 3] += v.vx * dt;
            positionsArr[i * 3 + 1] += v.vy * dt;
            positionsArr[i * 3 + 2] += v.vz * dt;
          }
        }
        geo.attributes.position.needsUpdate = true;
        points.material.opacity = runtime.playing ? 0.75 : 0.35;
      }
    }

    function updateConnections() {
      for (const obj of connectionLines) {
        if (obj.isMesh && obj.userData.a && obj.userData.b) {
          // Update tube
          const aPos = obj.userData.a.group.position;
          const bPos = obj.userData.b.group.position;
          const mid = new THREE.Vector3().addVectors(aPos, bPos).multiplyScalar(0.5);
          mid.y += 1.2;
          const curve = new THREE.QuadraticBezierCurve3(aPos.clone(), mid, bPos.clone());
          const newGeo = new THREE.TubeGeometry(curve, 48, 0.04, 8, false);
          obj.geometry.dispose();
          obj.geometry = newGeo;
          obj.material.opacity = runtime.playing ? 0.4 : 0.2;
        }
        if (obj.isPoints && obj.userData.curve) {
          // Update flow dots
          const curve = obj.userData.curve;
          const offsets = obj.userData.offsets;
          const flowPos = obj.geometry.attributes.position.array;
          for (let j = 0; j < offsets.length; j++) {
            offsets[j] = (offsets[j] + runtime.speed * 0.004) % 1;
            const pt = curve.getPointAt(offsets[j]);
            flowPos[j * 3] = pt.x;
            flowPos[j * 3 + 1] = pt.y;
            flowPos[j * 3 + 2] = pt.z;
          }
          obj.geometry.attributes.position.needsUpdate = true;
        }
      }
    }

    // ══════════════════════════════════════════════════════
    //  FRAME MANAGEMENT
    // ══════════════════════════════════════════════════════
    function updateFrame(index) {
      runtime.frameIndex = index;
      const frames = demo.frames || [];
      const frame = frames[index] || {};
      document.getElementById('frameLabel').textContent =
        `${index + 1} / ${frames.length} ${frame.label || ''}`;
      document.getElementById('frameNarrative').textContent = frame.narrative || '';
      document.getElementById('progress').style.width =
        `${Math.round(((index + 1) / Math.max(1, frames.length)) * 100)}%`;

      document.querySelectorAll('.step-btns button').forEach((btn, i) => {
        btn.classList.toggle('active', i === index);
      });

      const metrics = frame.metrics || {};
      runtime.force = Number(metrics.force ?? metrics.activity ?? runtime.force) || runtime.force;
      runtime.speed = Number(metrics.speed ?? runtime.speed) || runtime.speed;

      // Camera keyframe animation
      const kf = runtime.cameraKeyframes[index];
      if (kf && (kf.position || kf.target)) {
        if (kf.position) runtime.targetPosition.set(...vec3(kf.position, [9, 6, 13]));
        if (kf.target) runtime.targetLookAt.set(...vec3(kf.target, [0, 1, 0]));
        runtime.cameraAnimStart = runtime.elapsed;
        runtime.animatingCamera = true;
      }
    }

    function resetSimulation() {
      runtime.elapsed = 0;
      runtime.playing = false;
      updatePlayButton();
      for (const entry of simObjects.values()) {
        entry.group.position.set(...entry.initialPosition);
      }
      for (const emitter of particleEmitters) {
        for (const v of emitter.velocities) { v.age = v.life; }
      }
      updateFrame(0);
    }

    function togglePlay() {
      runtime.playing = !runtime.playing;
      updatePlayButton();
    }

    function updatePlayButton() {
      document.getElementById('play').textContent = runtime.playing ? '暂停' : '播放';
    }

    // ══════════════════════════════════════════════════════
    //  RAYCASTER INTERACTION
    // ══════════════════════════════════════════════════════
    function onCanvasMove(e) {
      mouse.x = (e.offsetX / canvas.clientWidth) * 2 - 1;
      mouse.y = -(e.offsetY / canvas.clientHeight) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(allMeshes, false);
      canvasWrap.classList.toggle('pointer', intersects.length > 0);
    }

    function onCanvasClick(e) {
      mouse.x = (e.offsetX / canvas.clientWidth) * 2 - 1;
      mouse.y = -(e.offsetY / canvas.clientHeight) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(allMeshes, false);
      if (intersects.length > 0) {
        const obj = intersects[0].object;
        if (obj.userData.spec) {
          selectObject(obj.userData.spec.id);
        }
      } else {
        deselectObject();
      }
    }

    function selectObject(id) {
      runtime.selectedId = id;
      const entry = simObjects.get(id);
      if (!entry) return;
      const spec = entry.spec;
      document.getElementById('inspectKind').textContent =
        `${spec.role || 'object'} · ${spec.shape || 'sphere'}`;
      document.getElementById('inspectLabel').textContent = spec.label || id;
      document.getElementById('inspectDetail').textContent =
        `质量: ${spec.mass ?? '—'} | 位置: (${entry.group.position.x.toFixed(1)}, ${entry.group.position.y.toFixed(1)}, ${entry.group.position.z.toFixed(1)})`;
      document.getElementById('inspectPopup').classList.add('open');

      // Highlight in side panel
      document.querySelectorAll('.object-row').forEach((row) => {
        row.classList.toggle('selected', row.dataset.objId === id);
      });
    }

    function deselectObject() {
      runtime.selectedId = null;
      document.getElementById('inspectPopup').classList.remove('open');
      document.querySelectorAll('.object-row').forEach((row) => row.classList.remove('selected'));
    }

    function closeInspect() { deselectObject(); }

    // ══════════════════════════════════════════════════════
    //  UI BUILDERS
    // ══════════════════════════════════════════════════════
    function buildInfoPanel() {
      document.getElementById('kind').textContent =
        `${sceneSpec.scene_kind || '3D Physics'} · Three.js`;
      document.getElementById('sceneKind').textContent =
        demo.demo_type || '';
      document.getElementById('title').textContent = demo.title || document.title;
      document.getElementById('description').textContent = demo.description || '';
      document.getElementById('goal').textContent = demo.learning_goal || '';
      document.getElementById('points').innerHTML =
        (demo.teaching_points || []).map((item) => `<li>${esc(String(item))}</li>`).join('')
        || '<li>观察 3D 场景中的对象交互与物理行为</li>';
      document.getElementById('tasks').innerHTML =
        (demo.student_tasks || []).map((item) => `<li>${esc(String(item))}</li>`).join('')
        || '<li>点击场景中的对象查看详情</li>';

      document.getElementById('objectList').innerHTML = sceneSpec.objects.map((obj, i) => `
        <div class="object-row" data-obj-id="${esc(obj.id || 'obj'+i)}" onclick="document.querySelector('#scene').dispatchEvent(new PointerEvent('click',{clientX:event.clientX,clientY:event.clientY}))">
          <i class="swatch" style="--color:${esc(obj.color || colorFromId(obj.id || 'obj'+i))}"></i>
          <span>${esc(obj.label || obj.id || '对象 '+ (i+1))}</span>
          <small style="color:#64748b">${esc(obj.role || obj.shape || '')}</small>
        </div>
      `).join('');
    }

    function buildStepButtons() {
      const frames = demo.frames || [];
      const container = document.getElementById('stepBtns');
      container.innerHTML = frames.map((f, i) =>
        `<button type="button" title="${esc(f.label || '步骤 '+(i+1))}">${i + 1}</button>`
      ).join('');
      container.querySelectorAll('button').forEach((btn, i) => {
        btn.addEventListener('click', () => {
          runtime.playing = false;
          updatePlayButton();
          updateFrame(i);
        });
      });
    }

    function buildControls() {
      const container = document.getElementById('controls');
      const controlsData = demo.controls || [];
      container.innerHTML = controlsData.map((ctrl, i) => `
        <label class="slider-row">
          <span class="head">
            <span>${esc(ctrl.label || ctrl.name)}</span>
            <output>${fmtNum(ctrl.default_value)}</output>
          </span>
          <input data-ctrl="${i}" type="range"
            min="${Number(ctrl.min_value ?? 0)}" max="${Number(ctrl.max_value ?? 1)}"
            step="${stepFor(ctrl)}" value="${Number(ctrl.default_value ?? 0.5)}" />
          <p>${esc(ctrl.description || '')}</p>
        </label>
      `).join('') || '<p>使用底部播放控制或点击 3D 对象进行交互。</p>';

      container.querySelectorAll('input[type="range"]').forEach((input, i) => {
        input.addEventListener('input', () => {
          const ctrl = controlsData[i] || {};
          const val = Number(input.value);
          const name = String(ctrl.name || '').toLowerCase();
          const row = input.closest('.slider-row');
          const out = row?.querySelector('output');
          if (out) out.textContent = fmtNum(val);
          if (name.includes('speed') || name.includes('速度')) runtime.speed = Math.max(0.1, val);
          else if (name.includes('damping') || name.includes('阻尼')) runtime.damping = Math.max(0, val);
          else if (name.includes('bloom') || name.includes('发光')) bloomPass.strength = val;
          else runtime.force = val;
        });
      });
    }

    // ══════════════════════════════════════════════════════
    //  UTILS
    // ══════════════════════════════════════════════════════
    function resize() {
      const rect = canvasWrap.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height, false);
      composer.setSize(rect.width, rect.height);
      camera.aspect = rect.width / Math.max(1, rect.height);
      camera.updateProjectionMatrix();
    }

    function vec3(value, fallback) {
      const raw = Array.isArray(value) && value.length === 3 ? value : fallback;
      return [Number(raw[0]) || 0, Number(raw[1]) || 0, Number(raw[2]) || 0];
    }

    function colorFromId(value) {
      let hash = 0;
      for (const ch of String(value)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
      const hue = hash % 360;
      return `hsl(${hue} 72% 56%)`;
    }

    function stepFor(ctrl) {
      const span = Math.abs(Number(ctrl.max_value) - Number(ctrl.min_value));
      if (span <= 1) return 0.01;
      if (span <= 10) return 0.1;
      return 1;
    }

    function esc(value) {
      return String(value).replace(/[&<>"']/g,
        (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[ch]);
    }

    function fmtNum(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return String(value ?? '');
      if (Math.abs(n) >= 100) return String(Math.round(n));
      if (Math.abs(n) >= 10) return n.toFixed(1);
      return n.toFixed(2).replace(/0$/, '').replace(/\.0$/, '');
    }
  </script>
</body>
</html>
"""
