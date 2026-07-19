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
      color: #172033;
      background: #f7f6f1;
      font-family: Aptos, "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
      --ink: #172033;
      --muted: #5d695f;
      --line: rgba(23, 32, 51, 0.12);
      --surface: #fffdfa;
      --surface-soft: #f7f6f1;
      --accent: #4f8b78;
      --amber: #d08a4f;
      --blue: #6377b6;
    }

    * { box-sizing: border-box; }

    html,
    body {
      width: 100%;
      min-width: 0;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: var(--surface-soft);
    }

    body {
      color: var(--ink);
    }

    .app {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(292px, 360px);
      gap: 14px;
      width: 100vw;
      height: 100vh;
      padding: 14px;
    }

    .stage,
    .side {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 253, 250, 0.96);
      box-shadow: 0 18px 42px rgba(23, 32, 51, 0.08);
    }

    .stage {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      overflow: hidden;
    }

    .head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 16px 18px 12px;
      border-bottom: 1px solid var(--line);
    }

    .eyebrow {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      color: var(--accent);
      font-size: 12px;
      font-weight: 850;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 0 9px;
      border: 1px solid rgba(79, 139, 120, 0.24);
      border-radius: 999px;
      background: #eef7f2;
      color: #315f50;
      white-space: nowrap;
    }

    h1 {
      margin: 7px 0 0;
      color: var(--ink);
      font-size: clamp(20px, 2.8vw, 30px);
      line-height: 1.16;
      letter-spacing: 0;
    }

    .frame-card {
      display: grid;
      min-width: 192px;
      max-width: 320px;
      gap: 5px;
      padding: 11px 12px;
      border: 1px solid rgba(79, 139, 120, 0.22);
      border-radius: 14px;
      background: #f4faf6;
    }

    .frame-card strong {
      color: var(--ink);
      font-size: 14px;
      line-height: 1.35;
    }

    .frame-card small {
      display: -webkit-box;
      overflow: hidden;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 3;
    }

    .canvas-shell {
      position: relative;
      min-height: 0;
      overflow: hidden;
      background:
        linear-gradient(rgba(23, 32, 51, 0.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(23, 32, 51, 0.045) 1px, transparent 1px),
        linear-gradient(135deg, #fffdfa, #f7f6f1);
      background-size: 28px 28px, 28px 28px, auto;
    }

    svg {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 420px;
    }

    .edge {
      fill: none;
      stroke: rgba(93, 105, 95, 0.42);
      stroke-linecap: round;
      stroke-width: 2.4;
      marker-end: url(#arrow);
      transition: opacity 220ms ease, stroke 220ms ease, stroke-width 220ms ease;
    }

    .edge.active {
      stroke: var(--accent);
      stroke-width: 4.2;
      stroke-dasharray: 10 12;
      animation: flow 1.2s linear infinite;
    }

    @keyframes flow {
      to { stroke-dashoffset: -44; }
    }

    .node {
      cursor: pointer;
      opacity: 0.7;
      transition: opacity 220ms ease, transform 220ms ease;
    }

    .node .body,
    .node .halo {
      transition: fill 220ms ease, stroke 220ms ease, opacity 220ms ease, transform 220ms ease;
    }

    .node.active {
      opacity: 1;
    }

    .node.active .halo {
      opacity: 0.38;
      animation: breathe 1.4s ease-in-out infinite;
    }

    @keyframes breathe {
      50% { transform: scale(1.08); }
    }

    .node-label {
      fill: var(--ink);
      font-size: 14px;
      font-weight: 850;
      pointer-events: none;
    }

    .node-detail {
      fill: var(--muted);
      font-size: 11px;
      pointer-events: none;
    }

    .node-kind {
      fill: #fffdfa;
      font-size: 10px;
      font-weight: 850;
      pointer-events: none;
    }

    .pulse {
      fill: var(--amber);
      opacity: 0;
      filter: url(#pulseGlow);
      transition: cx 360ms ease, cy 360ms ease, opacity 160ms ease;
    }

    .inspect {
      position: absolute;
      left: 14px;
      bottom: 14px;
      display: none;
      width: min(360px, calc(100% - 28px));
      gap: 7px;
      padding: 12px;
      border: 1px solid rgba(23, 32, 51, 0.12);
      border-radius: 14px;
      background: rgba(255, 253, 250, 0.94);
      box-shadow: 0 16px 36px rgba(23, 32, 51, 0.12);
      backdrop-filter: blur(14px);
    }

    .inspect.open {
      display: grid;
    }

    .inspect span {
      color: var(--accent);
      font-size: 12px;
      font-weight: 850;
    }

    .inspect strong {
      color: var(--ink);
      font-size: 16px;
      line-height: 1.35;
    }

    .inspect p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }

    .timeline {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 12px 16px 16px;
      border-top: 1px solid var(--line);
      background: rgba(255, 253, 250, 0.9);
    }

    button {
      min-height: 36px;
      border: 1px solid var(--accent);
      border-radius: 999px;
      padding: 0 14px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-size: 13px;
      font-weight: 850;
      cursor: pointer;
    }

    button.secondary {
      background: #fffdfa;
      color: var(--accent);
    }

    .rail {
      display: grid;
      gap: 8px;
      min-width: 0;
    }

    .bar {
      height: 9px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(79, 139, 120, 0.13);
    }

    .bar i {
      display: block;
      width: 0;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), var(--amber), var(--blue));
      transition: width 240ms ease;
    }

    .steps {
      display: flex;
      gap: 6px;
      min-width: 0;
      overflow-x: auto;
      padding-bottom: 1px;
    }

    .steps button {
      flex: 0 0 auto;
      min-height: 26px;
      max-width: 150px;
      overflow: hidden;
      padding: 0 10px;
      border-color: rgba(23, 32, 51, 0.1);
      background: #fffdfa;
      color: var(--muted);
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .steps button.active {
      border-color: rgba(79, 139, 120, 0.32);
      background: #eef7f2;
      color: #315f50;
    }

    .side {
      display: grid;
      align-content: start;
      gap: 12px;
      overflow: auto;
      padding: 14px;
    }

    .panel {
      display: grid;
      gap: 9px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 253, 250, 0.9);
    }

    .panel strong {
      color: var(--ink);
      font-size: 14px;
    }

    .panel p,
    .panel li,
    .slider-row {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }

    .panel ul {
      display: grid;
      gap: 6px;
      margin: 0;
      padding-left: 18px;
    }

    .metric-grid,
    .legend {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .metric,
    .legend-chip {
      min-width: 0;
      padding: 8px 9px;
      border: 1px solid rgba(23, 32, 51, 0.08);
      border-radius: 11px;
      background: #f8faf7;
    }

    .metric span,
    .legend-chip span {
      display: block;
      overflow: hidden;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .metric b {
      display: block;
      margin-top: 3px;
      color: var(--ink);
      font-size: 16px;
    }

    .legend-chip {
      display: flex;
      gap: 7px;
      align-items: center;
    }

    .dot {
      flex: 0 0 10px;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--chip-color, var(--accent));
    }

    .slider-row {
      display: grid;
      gap: 6px;
    }

    .slider-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--ink);
      font-weight: 800;
    }

    input[type="range"] {
      width: 100%;
      accent-color: var(--accent);
    }

    pre {
      max-height: 230px;
      overflow: auto;
      margin: 0;
      border-radius: 12px;
      padding: 12px;
      background: #172033;
      color: #e9f5ef;
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
    }

    @media (max-width: 920px) {
      html,
      body {
        overflow: auto;
      }

      .app {
        grid-template-columns: 1fr;
        height: auto;
        min-height: 100vh;
      }

      .stage {
        min-height: 76vh;
      }

      .head {
        grid-template-columns: 1fr;
      }

      .frame-card {
        max-width: none;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <main class="stage">
      <header class="head">
        <div>
          <div class="eyebrow">
            <span class="pill" id="kind">互动演示</span>
            <span class="pill" id="type">OpenMAIC-style</span>
          </div>
          <h1 id="title">__PAGE_TITLE__</h1>
        </div>
        <div class="frame-card">
          <strong id="frameLabel">准备演示</strong>
          <small id="frameNarrative">点击播放或选择步骤查看动态变化。</small>
        </div>
      </header>
      <section class="canvas-shell" id="canvasShell">
        <svg id="viz" role="img" aria-label="interactive visualization"></svg>
        <article class="inspect" id="inspect"></article>
      </section>
      <section class="timeline">
        <button id="play" type="button">播放</button>
        <div class="rail">
          <div class="bar"><i id="progress"></i></div>
          <div class="steps" id="steps"></div>
        </div>
        <button id="reset" type="button" class="secondary">重置</button>
      </section>
    </main>
    <aside class="side">
      <section class="panel"><strong>学习目标</strong><p id="goal"></p></section>
      <section class="panel"><strong>当前指标</strong><div class="metric-grid" id="metrics"></div></section>
      <section class="panel"><strong>节点图例</strong><div class="legend" id="legend"></div></section>
      <section class="panel"><strong>操作变量</strong><div id="controls"></div></section>
      <section class="panel"><strong>讲解要点</strong><ul id="points"></ul></section>
      <section class="panel"><strong>学习任务</strong><ul id="tasks"></ul></section>
      <section class="panel" id="codePanel" hidden><strong>可运行思路</strong><pre id="code"></pre></section>
    </aside>
  </div>
  <script id="demo-data" type="application/json">__DEMO_JSON__</script>
  <script>
    const demo = JSON.parse(document.getElementById('demo-data').textContent || '{}');
    const svg = document.getElementById('viz');
    const canvasShell = document.getElementById('canvasShell');
    const frames = Array.isArray(demo.frames) ? demo.frames : [];
    const nodes = (Array.isArray(demo.nodes) ? demo.nodes : []).map(normalizeNodeData);
    const edges = Array.isArray(demo.edges) ? demo.edges : [];
    const state = { playing: false, frame: 0, timer: null, speed: 1, layout: new Map(), selectedNodeId: null };

    const widgetLabels = {
      diagram: '关系图解',
      simulation: '动态模拟',
      code: '代码走读',
      timeline: '过程时间线',
      visualization3d: '三维演示'
    };
    const typeLabels = {
      concept_map: '概念网络',
      system_diagram: '系统结构',
      flowchart: '流程图',
      comparison_map: '对比图',
      algorithm_trace: '算法执行轨迹',
      data_flow: '数据流',
      process_simulation: '过程模拟',
      state_machine: '状态机',
      code_walkthrough: '代码走读',
      debug_trace: '调试轨迹',
      api_flow: 'API 流程',
      reproduction_demo: '复现实验',
      research_plan: '研究计划',
      experiment_schedule: '实验排期',
      paper_workflow: '论文流程',
      defense_process: '答辩流程'
    };

    document.getElementById('kind').textContent = widgetLabels[demo.widget_type] || demo.widget_type || '互动演示';
    document.getElementById('type').textContent = typeLabels[demo.demo_type] || demo.demo_type || 'OpenMAIC-style';
    document.getElementById('title').textContent = demo.title || document.title;
    document.getElementById('goal').textContent = demo.learning_goal || demo.description || '通过可视化步骤观察核心机制。';
    document.getElementById('points').innerHTML = listHtml(demo.teaching_points);
    document.getElementById('tasks').innerHTML = listHtml(demo.student_tasks);
    if (demo.code_snippet) {
      document.getElementById('codePanel').hidden = false;
      document.getElementById('code').textContent = demo.code_snippet;
    }

    renderSteps();
    renderLegend();
    buildControls();
    renderScene();
    showFrame(0);

    document.getElementById('play').addEventListener('click', () => {
      state.playing = !state.playing;
      document.getElementById('play').textContent = state.playing ? '暂停' : '播放';
      if (state.playing) tick();
      else clearTimeout(state.timer);
    });

    document.getElementById('reset').addEventListener('click', () => {
      state.playing = false;
      clearTimeout(state.timer);
      document.getElementById('play').textContent = '播放';
      showFrame(0);
    });

    const observer = new ResizeObserver(() => {
      renderScene();
      showFrame(state.frame);
    });
    observer.observe(canvasShell);

    function renderScene() {
      const rect = canvasShell.getBoundingClientRect();
      const width = Math.max(720, Math.round(rect.width || 1000));
      const height = Math.max(420, Math.round(rect.height || 620));
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      state.layout = computeLayout(width, height);
      svg.innerHTML = `
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#8a948e"></path>
          </marker>
          <filter id="soft"><feDropShadow dx="0" dy="10" stdDeviation="8" flood-color="#172033" flood-opacity=".13"/></filter>
          <filter id="pulseGlow"><feDropShadow dx="0" dy="0" stdDeviation="6" flood-color="#d08a4f" flood-opacity=".62"/></filter>
        </defs>
      `;
      const nodeById = new Map(nodes.map((node) => [node.id, node]));
      for (const edge of edges) {
        const from = state.layout.get(edge.source);
        const to = state.layout.get(edge.target);
        if (!from || !to) continue;
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('id', `edge-${cssId(edge.id || `${edge.source}->${edge.target}`)}`);
        path.setAttribute('class', 'edge');
        path.setAttribute('d', curvedPath(from, to));
        path.setAttribute('aria-label', edge.label || '');
        svg.appendChild(path);
      }
      for (const node of nodes) {
        const point = state.layout.get(node.id);
        if (!point) continue;
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.setAttribute('id', `node-${cssId(node.id)}`);
        group.setAttribute('class', 'node');
        group.setAttribute('transform', `translate(${point.x} ${point.y})`);
        group.innerHTML = nodeShape(node);
        group.addEventListener('click', () => inspectNode(node));
        svg.appendChild(group);
      }
      const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      pulse.setAttribute('id', 'pulse');
      pulse.setAttribute('class', 'pulse');
      pulse.setAttribute('r', '9');
      svg.appendChild(pulse);
    }

    function computeLayout(width, height) {
      const marginX = Math.min(130, width * 0.14);
      const marginY = Math.min(96, height * 0.16);
      const points = nodes.map((node, index) => ({
        id: node.id,
        x: marginX + (width - marginX * 2) * node.x / 100,
        y: marginY + (height - marginY * 2) * node.y / 100,
        vx: 0,
        vy: 0,
        index
      }));
      const byId = new Map(points.map((point) => [point.id, point]));
      if (points.length <= 1) return byId;
      for (let step = 0; step < 72; step += 1) {
        for (let i = 0; i < points.length; i += 1) {
          for (let j = i + 1; j < points.length; j += 1) {
            const a = points[i];
            const b = points[j];
            const dx = a.x - b.x || 0.01;
            const dy = a.y - b.y || 0.01;
            const dist2 = Math.max(900, dx * dx + dy * dy);
            const force = 5200 / dist2;
            const fx = dx * force;
            const fy = dy * force;
            a.vx += fx;
            a.vy += fy;
            b.vx -= fx;
            b.vy -= fy;
          }
        }
        for (const edge of edges) {
          const a = byId.get(edge.source);
          const b = byId.get(edge.target);
          if (!a || !b) continue;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.max(1, Math.hypot(dx, dy));
          const target = Math.min(260, Math.max(132, Math.sqrt(width * height) * 0.16));
          const force = (dist - target) * 0.006;
          const fx = dx / dist * force;
          const fy = dy / dist * force;
          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }
        for (const point of points) {
          point.vx += (width / 2 - point.x) * 0.001;
          point.vy += (height / 2 - point.y) * 0.001;
          point.x = clamp(point.x + point.vx, marginX, width - marginX);
          point.y = clamp(point.y + point.vy, marginY, height - marginY);
          point.vx *= 0.72;
          point.vy *= 0.72;
        }
      }
      return byId;
    }

    function showFrame(index) {
      if (!frames.length) return;
      state.frame = clamp(index, 0, frames.length - 1);
      const frame = frames[state.frame] || {};
      const activeNodes = new Set(frame.active_nodes || frame.activeNodes || []);
      const activeEdges = new Set(frame.active_edges || frame.activeEdges || []);
      document.getElementById('frameLabel').textContent = `${state.frame + 1} / ${frames.length} ${frame.label || ''}`;
      document.getElementById('frameNarrative').textContent = frame.narrative || '';
      document.getElementById('progress').style.width = `${Math.round(((state.frame + 1) / frames.length) * 100)}%`;
      document.querySelectorAll('.steps button').forEach((button, buttonIndex) => {
        button.classList.toggle('active', buttonIndex === state.frame);
      });
      document.querySelectorAll('.edge').forEach((edge) => edge.classList.remove('active'));
      activeEdges.forEach((id) => {
        const edge = document.getElementById(`edge-${cssId(id)}`);
        if (edge) edge.classList.add('active');
      });
      document.querySelectorAll('.node').forEach((node) => node.classList.remove('active'));
      activeNodes.forEach((id) => {
        const node = document.getElementById(`node-${cssId(id)}`);
        if (node) node.classList.add('active');
      });
      movePulse([...activeNodes]);
      renderMetrics(frame.metrics || {});
      if (state.selectedNodeId) {
        const node = nodes.find((item) => item.id === state.selectedNodeId);
        if (node) inspectNode(node);
      }
    }

    function movePulse(activeNodes) {
      const pulse = document.getElementById('pulse');
      const targetId = activeNodes[activeNodes.length - 1];
      const point = state.layout.get(targetId);
      if (!pulse || !point) {
        if (pulse) pulse.style.opacity = '0';
        return;
      }
      pulse.setAttribute('cx', String(point.x));
      pulse.setAttribute('cy', String(point.y - 58));
      pulse.style.opacity = '1';
    }

    function tick() {
      if (!state.playing) return;
      showFrame((state.frame + 1) % Math.max(1, frames.length));
      state.timer = setTimeout(tick, Math.max(650, 1850 / state.speed));
    }

    function renderSteps() {
      const container = document.getElementById('steps');
      container.innerHTML = frames.map((frame, index) => `
        <button type="button" title="${escapeHtml(frame.label || `步骤 ${index + 1}`)}">${escapeHtml(frame.label || `步骤 ${index + 1}`)}</button>
      `).join('');
      container.querySelectorAll('button').forEach((button, index) => {
        button.addEventListener('click', () => {
          state.playing = false;
          clearTimeout(state.timer);
          document.getElementById('play').textContent = '播放';
          showFrame(index);
        });
      });
    }

    function renderMetrics(metrics) {
      const entries = Object.entries(metrics).slice(0, 6);
      document.getElementById('metrics').innerHTML = entries.length
        ? entries.map(([name, value]) => `<div class="metric"><span>${escapeHtml(prettyMetric(name))}</span><b>${formatMetric(value)}</b></div>`).join('')
        : '<p>当前步骤暂无数值指标。</p>';
    }

    function renderLegend() {
      const kinds = new Map();
      for (const node of nodes) {
        if (!kinds.has(node.kind)) kinds.set(node.kind, node.color);
      }
      document.getElementById('legend').innerHTML = [...kinds.entries()].map(([kind, color]) => `
        <div class="legend-chip"><i class="dot" style="--chip-color:${escapeHtml(color)}"></i><span>${escapeHtml(prettyKind(kind))}</span></div>
      `).join('') || '<p>暂无节点图例。</p>';
    }

    function buildControls() {
      const controls = Array.isArray(demo.controls) ? demo.controls : [];
      document.getElementById('controls').innerHTML = controls.map((control, index) => {
        const min = Number(control.min_value ?? 0);
        const max = Number(control.max_value ?? 1);
        const value = Number(control.default_value ?? (min + max) / 2);
        return `
          <label class="slider-row">
            <span class="slider-head">
              <span>${escapeHtml(control.label || control.name || `变量 ${index + 1}`)}</span>
              <output>${formatMetric(value)}</output>
            </span>
            <input data-control="${index}" type="range" min="${min}" max="${max}" step="${stepFor(min, max)}" value="${value}" />
            <p>${escapeHtml(control.description || '')}</p>
          </label>
        `;
      }).join('') || '<p>本演示通过播放步骤呈现核心机制。</p>';
      document.querySelectorAll('input[type="range"]').forEach((input) => {
        input.addEventListener('input', () => {
          const row = input.closest('.slider-row');
          const output = row?.querySelector('output');
          const value = Number(input.value);
          if (output) output.textContent = formatMetric(value);
          const label = String(row?.querySelector('.slider-head span')?.textContent || '').toLowerCase();
          if (label.includes('速度') || label.includes('speed')) state.speed = Math.max(0.2, value || 1);
        });
      });
    }

    function inspectNode(node) {
      state.selectedNodeId = node.id;
      const incoming = edges.filter((edge) => edge.target === node.id).map((edge) => edge.label || edge.source);
      const outgoing = edges.filter((edge) => edge.source === node.id).map((edge) => edge.label || edge.target);
      const inspect = document.getElementById('inspect');
      inspect.classList.add('open');
      inspect.innerHTML = `
        <span>${escapeHtml(prettyKind(node.kind))}</span>
        <strong>${escapeHtml(node.label)}</strong>
        <p>${escapeHtml(node.detail || '')}</p>
        <p>${escapeHtml([incoming.length ? `前置：${incoming.join('、')}` : '', outgoing.length ? `流向：${outgoing.join('、')}` : ''].filter(Boolean).join('；'))}</p>
      `;
    }

    function normalizeNodeData(node, index) {
      const fallback = fallbackPosition(index);
      return {
        id: String(node.id || `node_${index + 1}`),
        label: String(node.label || node.title || `节点 ${index + 1}`),
        detail: String(node.detail || node.description || ''),
        kind: String(node.kind || node.type || 'concept'),
        x: finitePercent(node.x, fallback.x),
        y: finitePercent(node.y, fallback.y),
        color: validColor(node.color) ? node.color : palette(index)
      };
    }

    function fallbackPosition(index) {
      const angle = index * 1.618 * Math.PI;
      const radius = 28 + (index % 3) * 10;
      return {
        x: 50 + Math.cos(angle) * radius,
        y: 50 + Math.sin(angle) * radius
      };
    }

    function nodeShape(node) {
      const color = escapeHtml(node.color);
      const kind = escapeHtml(shortText(prettyKind(node.kind), 8));
      const label = escapeHtml(shortText(node.label, 13));
      const detail = escapeHtml(shortText(node.detail, 18));
      if (/(data|metric|指标|数据)/i.test(node.kind)) {
        return `
          <rect class="halo" x="-84" y="-50" width="168" height="100" rx="24" fill="${color}" opacity=".18"></rect>
          <rect class="body" x="-74" y="-42" width="148" height="84" rx="18" fill="#fffdfa" stroke="${color}" stroke-width="2.6" filter="url(#soft)"></rect>
          <rect x="-61" y="-32" width="56" height="20" rx="10" fill="${color}" opacity=".88"></rect>
          <text class="node-kind" x="-33" y="-18" text-anchor="middle">${kind}</text>
          <text class="node-label" text-anchor="middle" y="7">${label}</text>
          <text class="node-detail" text-anchor="middle" y="28">${detail}</text>
        `;
      }
      return `
        <circle class="halo" r="66" fill="${color}" opacity=".16"></circle>
        <circle class="body" r="54" fill="#fffdfa" stroke="${color}" stroke-width="2.8" filter="url(#soft)"></circle>
        <rect x="-36" y="-45" width="72" height="20" rx="10" fill="${color}" opacity=".88"></rect>
        <text class="node-kind" text-anchor="middle" y="-31">${kind}</text>
        <text class="node-label" text-anchor="middle" y="3">${label}</text>
        <text class="node-detail" text-anchor="middle" y="24">${detail}</text>
      `;
    }

    function curvedPath(from, to) {
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const lift = Math.min(95, Math.max(36, Math.abs(dy) * 0.35 + Math.abs(dx) * 0.08));
      return `M ${from.x} ${from.y} C ${from.x + dx * 0.35} ${from.y - lift}, ${from.x + dx * 0.65} ${to.y + lift}, ${to.x} ${to.y}`;
    }

    function listHtml(items) {
      const values = Array.isArray(items) ? items.filter(Boolean) : [];
      return values.length ? values.map((item) => `<li>${escapeHtml(String(item))}</li>`).join('') : '<li>围绕当前可视化观察关键变化。</li>';
    }

    function cssId(value) { return String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_'); }
    function clamp(value, min, max) { return Math.max(min, Math.min(max, Number(value) || 0)); }
    function finitePercent(value, fallback) {
      const num = Number(value);
      if (!Number.isFinite(num)) return fallback;
      return clamp(num <= 1 && num >= 0 ? num * 100 : num, 0, 100);
    }
    function validColor(value) { return /^#[0-9a-fA-F]{6}$/.test(String(value || '')); }
    function palette(index) {
      return ['#4f8b78', '#6f7fb7', '#d08a4f', '#8d6ab8', '#2f7ea8', '#b75f5f', '#6d8f46', '#c28b2e'][index % 8];
    }
    function prettyKind(value) {
      const labels = { concept: '概念', data: '数据', metric: '指标', state: '状态', step: '步骤', process: '过程', code: '代码', decision: '判断' };
      const key = String(value || 'concept').trim();
      return labels[key] || key.replace(/_/g, ' ');
    }
    function prettyMetric(name) {
      const labels = { progress: '进度', step: '步骤', accuracy: '准确率', loss: '损失', complexity: '复杂度', time: '时间', cost: '代价', confidence: '置信度' };
      const key = String(name || '').trim();
      return labels[key] || key.replace(/_/g, ' ');
    }
    function formatMetric(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return String(value ?? '');
      if (Math.abs(num) >= 100) return String(Math.round(num));
      if (Math.abs(num) >= 10) return num.toFixed(1).replace(/\\.0$/, '');
      return num.toFixed(2).replace(/0$/, '').replace(/\\.0$/, '');
    }
    function stepFor(min, max) {
      const span = Math.abs(Number(max) - Number(min));
      if (span <= 1) return 0.01;
      if (span <= 10) return 0.1;
      return 1;
    }
    function shortText(value, len) {
      const text = String(value || '');
      return text.length > len ? `${text.slice(0, len)}…` : text;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
    }
  </script>
</body>
</html>
"""
