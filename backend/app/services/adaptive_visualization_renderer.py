from __future__ import annotations

import html
import json
from typing import Any


def render_adaptive_visualization_html(demo: dict[str, Any], page_title: str) -> str:
    data_json = json.dumps(demo, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(page_title)
    return ADAPTIVE_VISUALIZATION_TEMPLATE.replace("__PAGE_TITLE__", safe_title).replace("__DEMO_JSON__", data_json)


ADAPTIVE_VISUALIZATION_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__PAGE_TITLE__</title>
  <style>
    :root {
      color: #111814;
      background: #fbfaf6;
      font-family: Aptos, "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      overflow: hidden;
      background:
        radial-gradient(circle at 12% 10%, rgba(7, 95, 86, 0.08), transparent 34rem),
        radial-gradient(circle at 88% 4%, rgba(154, 101, 0, 0.08), transparent 30rem),
        #fbfaf6;
    }
    .app {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      gap: 18px;
      height: 100vh;
      padding: 18px;
    }
    .stage, .side {
      border: 1px solid rgba(16, 23, 19, 0.14);
      background: rgba(255, 255, 255, 0.9);
      box-shadow: 0 18px 44px rgba(16, 23, 19, 0.08);
    }
    .stage {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-width: 0;
      overflow: hidden;
      border-radius: 22px;
    }
    .head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
      padding: 18px 20px 12px;
      border-bottom: 1px solid rgba(16, 23, 19, 0.1);
    }
    .head span {
      color: #075f56;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    h1 {
      margin: 6px 0 0;
      color: #111814;
      font-size: clamp(22px, 3vw, 38px);
      line-height: 1.05;
    }
    .status {
      min-width: 170px;
      border: 1px solid rgba(7, 95, 86, 0.18);
      border-radius: 16px;
      padding: 12px;
      background: #f7fbf8;
      text-align: right;
    }
    .status strong { display: block; color: #111814; font-size: 16px; }
    .status small { display: block; margin-top: 6px; color: #46544d; line-height: 1.45; }
    .canvas {
      position: relative;
      min-height: 0;
      overflow: hidden;
      padding: 20px;
    }
    svg {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 420px;
      border-radius: 18px;
      background: #fffdf8;
    }
    .node rect, .node circle, .node path {
      transition: transform 260ms ease, fill 260ms ease, stroke 260ms ease, opacity 260ms ease;
    }
    .node text {
      fill: #111814;
      font-weight: 800;
      font-size: 14px;
      pointer-events: none;
    }
    .edge {
      stroke: #80908a;
      stroke-width: 2.4;
      fill: none;
      marker-end: url(#arrow);
      transition: stroke 260ms ease, stroke-width 260ms ease, opacity 260ms ease;
    }
    .edge.active {
      stroke: #075f56;
      stroke-width: 4;
      opacity: 1;
    }
    .token {
      fill: #9a6500;
      opacity: 0;
      transition: cx 420ms ease, cy 420ms ease, opacity 220ms ease;
    }
    .timeline {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 14px 18px 18px;
      border-top: 1px solid rgba(16, 23, 19, 0.1);
    }
    button {
      min-height: 38px;
      border: 1px solid #075f56;
      border-radius: 999px;
      padding: 0 16px;
      background: #075f56;
      color: #fff;
      font-weight: 900;
      cursor: pointer;
    }
    button.secondary {
      background: #fff;
      color: #075f56;
    }
    .bar {
      height: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(7, 95, 86, 0.12);
    }
    .bar i {
      display: block;
      width: 0;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #075f56, #9a6500);
      transition: width 260ms ease;
    }
    .side {
      display: grid;
      align-content: start;
      gap: 14px;
      overflow: auto;
      border-radius: 22px;
      padding: 16px;
    }
    .panel {
      display: grid;
      gap: 8px;
      border: 1px solid rgba(16, 23, 19, 0.1);
      border-radius: 16px;
      padding: 12px;
      background: #fffdf8;
    }
    .panel strong { color: #111814; }
    .panel p, .panel li, .panel label {
      margin: 0;
      color: #46544d;
      font-size: 13px;
      line-height: 1.6;
    }
    .panel ul { margin: 0; padding-left: 18px; }
    .slider-row { display: grid; gap: 6px; }
    input[type="range"] { width: 100%; accent-color: #075f56; }
    pre {
      max-height: 260px;
      overflow: auto;
      margin: 0;
      border-radius: 14px;
      padding: 14px;
      background: #111814;
      color: #e7f4ef;
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-wrap;
    }
    @media (max-width: 980px) {
      body { overflow: auto; }
      .app { grid-template-columns: 1fr; height: auto; min-height: 100vh; }
      .stage { min-height: 76vh; }
      .head { grid-template-columns: 1fr; }
      .status { text-align: left; }
    }
  </style>
</head>
<body>
  <div class="app">
    <main class="stage">
      <header class="head">
        <div>
          <span id="kind"></span>
          <h1 id="title">__PAGE_TITLE__</h1>
        </div>
        <div class="status">
          <strong id="frameLabel"></strong>
          <small id="frameNarrative"></small>
        </div>
      </header>
      <section class="canvas">
        <svg id="viz" viewBox="0 0 1000 620" role="img" aria-label="interactive visualization"></svg>
      </section>
      <section class="timeline">
        <button id="play">播放</button>
        <div class="bar"><i id="progress"></i></div>
        <button id="reset" class="secondary">重置</button>
      </section>
    </main>
    <aside class="side">
      <section class="panel"><strong>学习目标</strong><p id="goal"></p></section>
      <section class="panel"><strong>操作变量</strong><div id="controls"></div></section>
      <section class="panel"><strong>讲解要点</strong><ul id="points"></ul></section>
      <section class="panel"><strong>学习任务</strong><ul id="tasks"></ul></section>
      <section class="panel" id="codePanel" hidden><strong>可运行思路</strong><pre id="code"></pre></section>
    </aside>
  </div>
  <script id="demo-data" type="application/json">__DEMO_JSON__</script>
  <script>
    const demo = JSON.parse(document.getElementById('demo-data').textContent);
    const svg = document.getElementById('viz');
    const frames = Array.isArray(demo.frames) ? demo.frames : [];
    const nodes = Array.isArray(demo.nodes) ? demo.nodes : [];
    const edges = Array.isArray(demo.edges) ? demo.edges : [];
    const state = { playing: false, frame: 0, timer: null, speed: 1 };

    document.getElementById('kind').textContent = `${demo.widget_type || demo.demo_type || 'interactive'} · OpenMAIC-style`;
    document.getElementById('title').textContent = demo.title || document.title;
    document.getElementById('goal').textContent = demo.learning_goal || demo.description || '';
    document.getElementById('points').innerHTML = (demo.teaching_points || []).map((item) => `<li>${escapeHtml(String(item))}</li>`).join('');
    document.getElementById('tasks').innerHTML = (demo.student_tasks || []).map((item) => `<li>${escapeHtml(String(item))}</li>`).join('');
    if (demo.code_snippet) {
      document.getElementById('codePanel').hidden = false;
      document.getElementById('code').textContent = demo.code_snippet;
    }

    validateDemo();
    renderSvg();
    buildControls();
    showFrame(0);

    document.getElementById('play').onclick = () => {
      state.playing = !state.playing;
      document.getElementById('play').textContent = state.playing ? '暂停' : '播放';
      if (state.playing) tick();
      else clearTimeout(state.timer);
    };
    document.getElementById('reset').onclick = () => {
      state.playing = false;
      clearTimeout(state.timer);
      document.getElementById('play').textContent = '播放';
      showFrame(0);
    };

    function renderSvg() {
      const safeNodes = nodes;
      const safeEdges = edges;
      svg.innerHTML = `
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#80908a"></path>
          </marker>
          <filter id="soft"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#101713" flood-opacity=".12"/></filter>
        </defs>
      `;
      const nodeById = new Map(safeNodes.map((node) => [node.id, normalizeNode(node)]));
      for (const edge of safeEdges) {
        const from = nodeById.get(edge.source);
        const to = nodeById.get(edge.target);
        if (!from || !to) continue;
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('id', `edge-${cssId(edge.id || `${edge.source}->${edge.target}`)}`);
        path.setAttribute('class', 'edge');
        path.setAttribute('d', `M ${from.x} ${from.y} C ${(from.x + to.x) / 2} ${from.y}, ${(from.x + to.x) / 2} ${to.y}, ${to.x} ${to.y}`);
        svg.appendChild(path);
      }
      for (const node of nodeById.values()) {
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.setAttribute('id', `node-${cssId(node.id)}`);
        group.setAttribute('class', 'node');
        group.setAttribute('transform', `translate(${node.x} ${node.y})`);
        group.innerHTML = nodeShape(node);
        svg.appendChild(group);
      }
      const token = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      token.setAttribute('id', 'token');
      token.setAttribute('class', 'token');
      token.setAttribute('r', '11');
      svg.appendChild(token);
    }

    function showFrame(index) {
      state.frame = Math.max(0, Math.min(index, Math.max(0, frames.length - 1)));
      const frame = frames[state.frame] || {};
      document.getElementById('frameLabel').textContent = `${state.frame + 1} / ${Math.max(1, frames.length)} ${frame.label || ''}`;
      document.getElementById('frameNarrative').textContent = frame.narrative || '';
      document.getElementById('progress').style.width = `${Math.round(((state.frame + 1) / Math.max(1, frames.length)) * 100)}%`;
      document.querySelectorAll('.edge').forEach((edge) => edge.classList.remove('active'));
      (frame.active_edges || frame.activeEdges || []).forEach((id) => {
        const edge = document.getElementById(`edge-${cssId(id)}`);
        if (edge) edge.classList.add('active');
      });
      document.querySelectorAll('.node').forEach((node) => node.style.opacity = '.74');
      (frame.active_nodes || frame.activeNodes || []).forEach((id) => {
        const node = document.getElementById(`node-${cssId(id)}`);
        if (node) node.style.opacity = '1';
      });
      const token = document.getElementById('token');
      const activeNodes = frame.active_nodes || frame.activeNodes || [];
      const targetNode = activeNodes.length ? document.getElementById(`node-${cssId(activeNodes[activeNodes.length - 1])}`) : null;
      if (targetNode) {
        const match = targetNode.getAttribute('transform').match(/translate\\(([-\\d.]+) ([-\\d.]+)\\)/);
        if (match) {
          token.setAttribute('cx', String(Number(match[1])));
          token.setAttribute('cy', String(Number(match[2]) - 62));
          token.style.opacity = '1';
        }
      } else {
        token.style.opacity = '0';
      }
    }

    function tick() {
      if (!state.playing) return;
      showFrame((state.frame + 1) % Math.max(1, frames.length));
      state.timer = setTimeout(tick, Math.max(700, 1800 / state.speed));
    }

    function buildControls() {
      const controls = Array.isArray(demo.controls) ? demo.controls : [];
      document.getElementById('controls').innerHTML = controls.map((control, index) => `
        <label class="slider-row">
          <span>${escapeHtml(control.label || control.name || `变量 ${index + 1}`)}</span>
          <input data-control="${index}" type="range" min="${Number(control.min_value ?? 0)}" max="${Number(control.max_value ?? 1)}" step="${stepFor(control)}" value="${Number(control.default_value ?? 0.5)}" />
          <p>${escapeHtml(control.description || '')}</p>
        </label>
      `).join('') || '<p>本演示通过播放步骤呈现核心机制。</p>';
      document.querySelectorAll('input[type="range"]').forEach((input) => {
        input.addEventListener('input', () => {
          const name = String(input.previousElementSibling?.textContent || '').toLowerCase();
          if (name.includes('速度') || name.includes('speed')) state.speed = Math.max(0.2, Number(input.value) || 1);
        });
      });
    }

    function normalizeNode(node) {
      const angle = 0;
      const radiusX = 0;
      const radiusY = 0;
      return {
        id: node.id,
        label: node.label,
        detail: node.detail,
        x: 120 + Number(node.x) * 7.6,
        y: 80 + Number(node.y) * 4.6,
        kind: node.kind,
        color: node.color
      };
    }

    function nodeShape(node) {
      if (node.kind === 'data' || node.kind === 'metric') {
        return `<rect x="-72" y="-42" width="144" height="84" rx="18" fill="${escapeHtml(node.color)}" opacity=".18" stroke="${escapeHtml(node.color)}" stroke-width="3" filter="url(#soft)"></rect><text text-anchor="middle" y="-3">${escapeHtml(shortText(node.label, 12))}</text><text text-anchor="middle" y="22" fill="#46544d" font-size="11">${escapeHtml(shortText(node.detail, 16))}</text>`;
      }
      return `<circle r="56" fill="${escapeHtml(node.color)}" opacity=".18" stroke="${escapeHtml(node.color)}" stroke-width="3" filter="url(#soft)"></circle><text text-anchor="middle" y="-4">${escapeHtml(shortText(node.label, 10))}</text><text text-anchor="middle" y="22" fill="#46544d" font-size="11">${escapeHtml(shortText(node.detail, 14))}</text>`;
    }

    function validateDemo() {
      if (!nodes.length || !edges.length || !frames.length) {
        throw new Error('Invalid interactive visualization: nodes, edges and frames are required.');
      }
      const nodeIds = new Set(nodes.map((node) => node.id));
      const edgeIds = new Set(edges.map((edge) => edge.id || `${edge.source}->${edge.target}`));
      for (const edge of edges) {
        if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
          throw new Error(`Invalid interactive visualization edge: ${edge.source}->${edge.target}`);
        }
      }
      for (const frame of frames) {
        for (const id of frame.active_nodes || frame.activeNodes || []) {
          if (!nodeIds.has(id)) throw new Error(`Invalid frame node reference: ${id}`);
        }
        for (const id of frame.active_edges || frame.activeEdges || []) {
          if (!edgeIds.has(id)) throw new Error(`Invalid frame edge reference: ${id}`);
        }
      }
    }
    function cssId(value) { return String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_'); }
    function shortText(value, len) {
      const text = String(value || '');
      return text.length > len ? `${text.slice(0, len)}…` : text;
    }
    function stepFor(control) {
      const span = Math.abs(Number(control.max_value ?? 1) - Number(control.min_value ?? 0));
      if (span <= 1) return 0.01;
      if (span <= 10) return 0.1;
      return 1;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
    }
  </script>
</body>
</html>
"""
