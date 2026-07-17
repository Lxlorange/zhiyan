from __future__ import annotations

import html
import json
from typing import Any


def render_three_physics_html(demo: dict[str, Any], page_title: str) -> str:
    data_json = json.dumps(demo, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(page_title)
    return THREE_PHYSICS_TEMPLATE.replace("__PAGE_TITLE__", safe_title).replace("__DEMO_JSON__", data_json)


THREE_PHYSICS_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__PAGE_TITLE__</title>
  <style>
    :root {
      color: #172033;
      background: #eef4ff;
      font-family: Inter, "Microsoft YaHei", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      overflow: hidden;
      background:
        radial-gradient(circle at 18% 12%, rgba(56, 189, 248, 0.2), transparent 30%),
        radial-gradient(circle at 85% 20%, rgba(34, 197, 94, 0.18), transparent 30%),
        linear-gradient(135deg, #f8fbff 0%, #eef4ff 48%, #f7fee7 100%);
    }
    .app {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      height: 100vh;
      gap: 16px;
      padding: 16px;
    }
    .stage {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 10px;
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(91, 141, 239, 0.28);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.68);
      box-shadow: 0 24px 80px rgba(37, 99, 235, 0.16);
    }
    .canvas-wrap {
      position: relative;
      min-height: 0;
      overflow: hidden;
      border-radius: 0 0 16px 16px;
    }
    #scene {
      width: 100%;
      height: 100%;
      display: block;
    }
    .hud {
      position: static;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      padding: 14px 14px 0;
    }
    .title-card, .status-card, .side {
      border: 1px solid rgba(148, 163, 184, 0.22);
      background: rgba(255, 255, 255, 0.86);
      backdrop-filter: blur(18px);
      box-shadow: 0 14px 40px rgba(15, 23, 42, 0.1);
    }
    .title-card {
      min-width: 0;
      border-radius: 16px;
      padding: 12px 14px;
    }
    .title-card span {
      display: block;
      color: #2563eb;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    .title-card h1 {
      margin: 6px 0 0;
      color: #111827;
      font-size: 18px;
      line-height: 1.25;
    }
    .title-card p {
      margin: 8px 0 0;
      color: #475569;
      font-size: 12px;
      line-height: 1.42;
      display: -webkit-box;
      overflow: hidden;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }
    .status-card {
      min-width: 180px;
      border-radius: 16px;
      padding: 12px 14px;
      text-align: right;
    }
    .status-card strong {
      display: block;
      color: #111827;
      font-size: 16px;
    }
    .status-card small {
      display: block;
      color: #64748b;
      margin-top: 5px;
      line-height: 1.4;
      display: -webkit-box;
      overflow: hidden;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 3;
    }
    .timeline {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      margin: 0 14px 14px;
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 16px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.86);
      backdrop-filter: blur(18px);
      box-shadow: 0 14px 40px rgba(15, 23, 42, 0.1);
    }
    button {
      height: 38px;
      padding: 0 14px;
      border: 1px solid #2563eb;
      border-radius: 11px;
      background: #2563eb;
      color: white;
      font-weight: 900;
      cursor: pointer;
    }
    button.secondary {
      background: white;
      color: #1d4ed8;
    }
    .bar {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: #dbeafe;
    }
    .bar i {
      display: block;
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #2563eb, #22c55e);
      transition: width 260ms ease;
    }
    .side {
      overflow: auto;
      border-radius: 18px;
      padding: 16px;
      display: grid;
      align-content: start;
      gap: 14px;
    }
    .panel {
      display: grid;
      gap: 8px;
      border-radius: 14px;
      padding: 12px;
      background: rgba(248, 251, 255, 0.92);
      border: 1px solid rgba(203, 213, 225, 0.7);
    }
    .panel strong {
      color: #111827;
      font-size: 14px;
    }
    .panel p, .panel li, .panel label {
      margin: 0;
      color: #475569;
      font-size: 13px;
      line-height: 1.55;
    }
    .panel ul {
      margin: 0;
      padding-left: 18px;
    }
    .object-list {
      display: grid;
      gap: 8px;
    }
    .object-row {
      display: grid;
      grid-template-columns: 12px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      color: #334155;
      font-size: 13px;
    }
    .swatch {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: var(--color);
    }
    .slider-row {
      display: grid;
      gap: 6px;
    }
    input[type="range"] {
      width: 100%;
      accent-color: #2563eb;
    }
    .narrative {
      color: #1e293b;
      font-size: 14px;
      line-height: 1.65;
    }
    @media (max-width: 960px) {
      body { overflow: auto; }
      .app { grid-template-columns: 1fr; height: auto; min-height: 100vh; }
      .stage { min-height: 78vh; }
      .hud { grid-template-columns: 1fr; }
      .status-card { text-align: left; }
    }
  </style>
  <script type="importmap">
    {
      "imports": {
        "three": "https://esm.sh/three@0.167.1",
        "three/addons/": "https://esm.sh/three@0.167.1/examples/jsm/",
        "cannon-es": "https://esm.sh/cannon-es@0.20.0"
      }
    }
  </script>
</head>
<body>
  <div class="app">
    <main class="stage">
      <section class="hud">
        <div class="title-card">
          <span id="kind"></span>
          <h1 id="title">__PAGE_TITLE__</h1>
          <p id="description"></p>
        </div>
        <div class="status-card">
          <strong id="frameLabel"></strong>
          <small id="frameNarrative"></small>
        </div>
      </section>
      <div class="canvas-wrap">
        <canvas id="scene"></canvas>
      </div>
      <section class="timeline">
        <button id="play">Play</button>
        <div class="bar"><i id="progress"></i></div>
        <button id="reset" class="secondary">Reset</button>
      </section>
    </main>
    <aside class="side">
      <section class="panel">
        <strong>Learning Goal</strong>
        <p id="goal"></p>
      </section>
      <section class="panel">
        <strong>Scene Objects</strong>
        <div class="object-list" id="objectList"></div>
      </section>
      <section class="panel">
        <strong>Physics Controls</strong>
        <div id="controls"></div>
      </section>
      <section class="panel">
        <strong>Teaching Points</strong>
        <ul id="points"></ul>
      </section>
      <section class="panel">
        <strong>Student Tasks</strong>
        <ul id="tasks"></ul>
      </section>
    </aside>
  </div>
  <script id="demo-data" type="application/json">__DEMO_JSON__</script>
  <script type="module">
    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
    import * as CANNON from 'cannon-es';

    const demo = JSON.parse(document.getElementById('demo-data').textContent);
    const sceneSpec = demo.physics_scene;
    if (!sceneSpec || !Array.isArray(sceneSpec.objects) || !sceneSpec.objects.length) {
      throw new Error('Missing physics_scene.objects; cannot render the 3D physics demo.');
    }

    const canvas = document.getElementById('scene');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fbff);
    scene.fog = new THREE.Fog(0xf8fbff, 18, 52);

    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 160);
    const cameraConfig = sceneSpec.camera || {};
    camera.position.set(...vec3(cameraConfig.position, [8, 7, 11]));

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(...vec3(cameraConfig.target, [0, 1, 0]));
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    const hemi = new THREE.HemisphereLight(0xdbeafe, 0x1e293b, 1.4);
    scene.add(hemi);
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
    keyLight.position.set(8, 12, 8);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    scene.add(keyLight);

    const world = new CANNON.World({
      gravity: new CANNON.Vec3(...vec3(sceneSpec.gravity, [0, -9.82, 0]))
    });
    world.broadphase = new CANNON.SAPBroadphase(world);
    world.allowSleep = true;

    const defaultMaterial = new CANNON.Material('default');
    const contact = new CANNON.ContactMaterial(defaultMaterial, defaultMaterial, {
      friction: 0.36,
      restitution: 0.38
    });
    world.defaultContactMaterial = contact;
    world.addContactMaterial(contact);

    const floorBody = new CANNON.Body({ mass: 0, material: defaultMaterial });
    floorBody.addShape(new CANNON.Box(new CANNON.Vec3(18, 0.08, 18)));
    floorBody.position.set(0, -0.08, 0);
    world.addBody(floorBody);

    const floorMesh = new THREE.Mesh(
      new THREE.BoxGeometry(36, 0.12, 36),
      new THREE.MeshStandardMaterial({ color: 0xeaf2ff, roughness: 0.82, metalness: 0.02 })
    );
    floorMesh.receiveShadow = true;
    floorMesh.position.y = -0.08;
    scene.add(floorMesh);

    const grid = new THREE.GridHelper(36, 36, 0x94a3b8, 0xdbeafe);
    grid.position.y = 0.01;
    scene.add(grid);

    const simObjects = new Map();
    const trails = new Map();
    const labels = [];
    const clock = new THREE.Clock();
    const runtime = {
      playing: false,
      speed: 1,
      force: 1,
      damping: 0.08,
      frameIndex: 0,
      elapsed: 0
    };

    for (const spec of sceneSpec.objects) {
      const entry = createSimObject(spec);
      simObjects.set(spec.id, entry);
      scene.add(entry.mesh);
      world.addBody(entry.body);
      if (entry.label) labels.push(entry.label);
      trails.set(spec.id, createTrail(spec.color || '#2563eb'));
    }

    for (const trail of trails.values()) scene.add(trail.line);
    createConnections();
    buildInfoPanel();
    buildControls();
    updateFrame(0);

    window.addEventListener('resize', resize);
    document.getElementById('play').onclick = () => {
      runtime.playing = !runtime.playing;
      document.getElementById('play').textContent = runtime.playing ? 'Pause' : 'Play';
    };
    document.getElementById('reset').onclick = resetSimulation;
    resize();
    animate();

    function createSimObject(spec) {
      const size = vec3(spec.size, [1, 1, 1]);
      const position = vec3(spec.position, [0, 2, 0]);
      const velocity = vec3(spec.velocity, [0, 0, 0]);
      const mass = Number.isFinite(Number(spec.mass)) ? Number(spec.mass) : 1;
      const color = new THREE.Color(spec.color || colorFromString(spec.id || spec.label || 'object'));
      const material = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.46,
        metalness: 0.16,
        emissive: color.clone().multiplyScalar(0.08)
      });
      const shapeType = String(spec.shape || 'sphere').toLowerCase();
      let geometry;
      let shape;
      if (shapeType === 'box' || shapeType === 'cube' || shapeType === 'packet') {
        geometry = new THREE.BoxGeometry(size[0], size[1], size[2]);
        shape = new CANNON.Box(new CANNON.Vec3(size[0] / 2, size[1] / 2, size[2] / 2));
      } else if (shapeType === 'cylinder' || shapeType === 'node') {
        geometry = new THREE.CylinderGeometry(size[0] / 2, size[0] / 2, size[1], 32);
        shape = new CANNON.Cylinder(size[0] / 2, size[0] / 2, size[1], 32);
      } else {
        const radius = Math.max(0.18, size[0] / 2);
        geometry = new THREE.SphereGeometry(radius, 40, 28);
        shape = new CANNON.Sphere(radius);
      }
      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const body = new CANNON.Body({ mass, material: defaultMaterial, linearDamping: runtime.damping, angularDamping: runtime.damping });
      body.addShape(shape);
      body.position.set(...position);
      body.velocity.set(...velocity);
      body.userData = { initialPosition: position, initialVelocity: velocity, spec };

      const label = createLabel(spec.label || spec.id || 'Object', color.getStyle());
      label.position.set(position[0], position[1] + size[1] * 0.9 + 0.35, position[2]);
      scene.add(label);
      return { spec, mesh, body, label };
    }

    function createLabel(text, color) {
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 128;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = 'rgba(255,255,255,0.86)';
      roundRect(ctx, 12, 20, 488, 78, 30);
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 5;
      ctx.stroke();
      ctx.fillStyle = '#172033';
      ctx.font = '700 34px Microsoft YaHei, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(text).slice(0, 18), 256, 60);
      const texture = new THREE.CanvasTexture(canvas);
      const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
      const sprite = new THREE.Sprite(material);
      sprite.scale.set(2.4, 0.6, 1);
      return sprite;
    }

    function createTrail(color) {
      const maxPoints = 120;
      const geometry = new THREE.BufferGeometry();
      const positions = new Float32Array(maxPoints * 3);
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geometry.setDrawRange(0, 0);
      const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55 }));
      return { line, positions, points: [], maxPoints };
    }

    function createConnections() {
      const objects = Array.from(simObjects.values());
      for (let i = 1; i < objects.length; i++) {
        const a = objects[i - 1];
        const b = objects[i];
        const spring = new CANNON.Spring(a.body, b.body, {
          restLength: 2.4,
          stiffness: 18,
          damping: 1.2
        });
        spring.applyForce = spring.applyForce.bind(spring);
        world.addEventListener('postStep', spring.applyForce);
        const geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
        const material = new THREE.LineBasicMaterial({ color: 0x60a5fa, transparent: true, opacity: 0.42 });
        const line = new THREE.Line(geometry, material);
        line.userData = { a, b };
        scene.add(line);
      }
    }

    function animate() {
      requestAnimationFrame(animate);
      const dt = Math.min(0.033, clock.getDelta()) * runtime.speed;
      if (runtime.playing) {
        runtime.elapsed += dt;
        applyTopicForces(dt);
        world.step(1 / 60, dt, 4);
        const nextFrame = Math.floor(runtime.elapsed / 2.2) % Math.max(1, demo.frames.length);
        if (nextFrame !== runtime.frameIndex) updateFrame(nextFrame);
      }
      syncMeshes();
      controls.update();
      renderer.render(scene, camera);
    }

    function applyTopicForces(dt) {
      const type = String(demo.demo_type || sceneSpec.scene_kind || '').toLowerCase();
      const entries = Array.from(simObjects.values());
      entries.forEach((entry, index) => {
        const body = entry.body;
        body.linearDamping = runtime.damping;
        body.angularDamping = runtime.damping;
        const t = runtime.elapsed + index * 0.7;
        if (type.includes('signal') || type.includes('wave') || type.includes('csi')) {
          body.applyForce(new CANNON.Vec3(Math.sin(t * 2.2) * 12 * runtime.force, Math.cos(t * 1.7) * 8, Math.sin(t * 2.8) * 10), body.position);
        } else if (type.includes('network') || type.includes('packet') || type.includes('graph')) {
          const targetX = (index - (entries.length - 1) / 2) * 2.2;
          const targetZ = Math.sin(t) * 2.5;
          body.applyForce(new CANNON.Vec3((targetX - body.position.x) * 14 * runtime.force, 4, (targetZ - body.position.z) * 14), body.position);
        } else if (type.includes('neural') || type.includes('activation')) {
          body.applyImpulse(new CANNON.Vec3(Math.sin(t) * 0.08 * runtime.force, Math.max(0, Math.sin(t * 1.4)) * 0.18, Math.cos(t) * 0.08), body.position);
        } else {
          body.applyForce(new CANNON.Vec3(Math.sin(t) * 6 * runtime.force, Math.cos(t * 0.8) * 5, Math.cos(t) * 6), body.position);
        }
      });
    }

    function syncMeshes() {
      for (const [id, entry] of simObjects.entries()) {
        entry.mesh.position.copy(entry.body.position);
        entry.mesh.quaternion.copy(entry.body.quaternion);
        entry.label.position.set(entry.body.position.x, entry.body.position.y + 0.9, entry.body.position.z);
        updateTrail(id, entry.body.position);
      }
      scene.children.forEach((child) => {
        if (child.isLine && child.userData && child.userData.a) {
          const points = [
            child.userData.a.body.position,
            child.userData.b.body.position
          ].map((p) => new THREE.Vector3(p.x, p.y, p.z));
          child.geometry.setFromPoints(points);
        }
      });
    }

    function updateTrail(id, position) {
      const trail = trails.get(id);
      if (!trail) return;
      trail.points.push(position.clone());
      if (trail.points.length > trail.maxPoints) trail.points.shift();
      trail.points.forEach((point, index) => {
        trail.positions[index * 3] = point.x;
        trail.positions[index * 3 + 1] = point.y;
        trail.positions[index * 3 + 2] = point.z;
      });
      trail.line.geometry.setDrawRange(0, trail.points.length);
      trail.line.geometry.attributes.position.needsUpdate = true;
    }

    function updateFrame(index) {
      runtime.frameIndex = index;
      const frame = demo.frames[index] || {};
      document.getElementById('frameLabel').textContent = `${index + 1} / ${demo.frames.length} ${frame.label || ''}`;
      document.getElementById('frameNarrative').textContent = frame.narrative || '';
      document.getElementById('progress').style.width = `${Math.round(((index + 1) / Math.max(1, demo.frames.length)) * 100)}%`;
      const metrics = frame.metrics || {};
      runtime.force = Number(metrics.force ?? metrics.activity ?? runtime.force) || runtime.force;
    }

    function resetSimulation() {
      runtime.elapsed = 0;
      updateFrame(0);
      for (const entry of simObjects.values()) {
        const initialPosition = entry.body.userData.initialPosition;
        const initialVelocity = entry.body.userData.initialVelocity;
        entry.body.position.set(...initialPosition);
        entry.body.velocity.set(...initialVelocity);
        entry.body.angularVelocity.set(0, 0, 0);
        entry.body.quaternion.set(0, 0, 0, 1);
      }
      for (const trail of trails.values()) {
        trail.points = [];
        trail.line.geometry.setDrawRange(0, 0);
      }
    }

    function buildInfoPanel() {
      document.getElementById('kind').textContent = `${demo.demo_type || '3D Physics'} · Three.js + cannon-es`;
      document.getElementById('title').textContent = demo.title || document.title;
      document.getElementById('description').textContent = demo.description || '';
      document.getElementById('goal').textContent = demo.learning_goal || '';
      document.getElementById('points').innerHTML = (demo.teaching_points || []).map((item) => `<li>${escapeHtml(String(item))}</li>`).join('');
      document.getElementById('tasks').innerHTML = (demo.student_tasks || []).map((item) => `<li>${escapeHtml(String(item))}</li>`).join('');
      document.getElementById('objectList').innerHTML = sceneSpec.objects.map((item) => `
        <div class="object-row">
          <i class="swatch" style="--color:${escapeHtml(item.color || colorFromString(item.id || item.label || 'object'))}"></i>
          <span>${escapeHtml(item.label || item.id)} · ${escapeHtml(item.role || item.shape || 'object')}</span>
        </div>
      `).join('');
    }

    function buildControls() {
      const container = document.getElementById('controls');
      const controlsData = demo.controls || [];
      container.innerHTML = controlsData.map((control, index) => `
        <label class="slider-row">
          <span>${escapeHtml(control.label || control.name)}</span>
          <input data-control="${index}" type="range" min="${Number(control.min_value)}" max="${Number(control.max_value)}" step="${stepFor(control)}" value="${Number(control.default_value)}" />
          <p>${escapeHtml(control.description || '')}</p>
        </label>
      `).join('');
      container.querySelectorAll('input[type="range"]').forEach((input, index) => {
        input.addEventListener('input', () => {
          const control = controlsData[index] || {};
          const value = Number(input.value);
          const name = String(control.name || '').toLowerCase();
          if (name.includes('speed') || name.includes('閫熷害')) runtime.speed = Math.max(0.1, value);
          else if (name.includes('gravity') || name.includes('閲嶅姏')) world.gravity.set(0, -Math.abs(value), 0);
          else if (name.includes('damping') || name.includes('闃诲凹')) runtime.damping = Math.max(0, value);
          else runtime.force = value;
        });
      });
    }

    function stepFor(control) {
      const span = Math.abs(Number(control.max_value) - Number(control.min_value));
      if (span <= 1) return 0.01;
      if (span <= 10) return 0.1;
      return 1;
    }

    function resize() {
      const rect = canvas.parentElement.getBoundingClientRect();
      renderer.setSize(rect.width, rect.height, false);
      camera.aspect = rect.width / Math.max(1, rect.height);
      camera.updateProjectionMatrix();
    }

    function vec3(value, requiredValue) {
      const raw = Array.isArray(value) ? value : requiredValue;
      return [Number(raw[0]) || 0, Number(raw[1]) || 0, Number(raw[2]) || 0];
    }

    function colorFromString(value) {
      let hash = 0;
      for (const ch of String(value)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
      const hue = hash % 360;
      return `hsl(${hue} 78% 52%)`;
    }

    function escapeHtml(value) {
      return value.replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
    }

    function roundRect(ctx, x, y, width, height, radius) {
      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.arcTo(x + width, y, x + width, y + height, radius);
      ctx.arcTo(x + width, y + height, x, y + height, radius);
      ctx.arcTo(x, y + height, x, y, radius);
      ctx.arcTo(x, y, x + width, y, radius);
      ctx.closePath();
    }
  </script>
</body>
</html>
"""

