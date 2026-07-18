<template>
  <section class="knowledge-sphere-panel">
    <header class="knowledge-sphere-toolbar">
      <div class="knowledge-sphere-toolbar__title">
        <strong>知识漏斗</strong>
        <span>{{ graphStats }}</span>
      </div>
      <div class="knowledge-sphere-toolbar__controls">
        <el-select
          :model-value="projectId"
          clearable
          placeholder="全部项目与资料"
          class="knowledge-sphere-select"
          @update:model-value="updateProjectId"
        >
          <el-option
            v-for="project in projectOptions"
            :key="project.id"
            :label="project.title"
            :value="project.id"
          />
        </el-select>
        <el-input
          :model-value="query"
          class="knowledge-sphere-search"
          placeholder="搜索知识点、项目目标或资料片段"
          clearable
          @update:model-value="updateQuery"
          @keyup.enter="emit('search')"
        />
        <div class="knowledge-sphere-segments" role="group" aria-label="知识漏斗视图">
          <button
            v-for="option in viewOptions"
            :key="option.value"
            type="button"
            :class="{ active: viewMode === option.value }"
            @click="viewMode = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <el-button :loading="loading" type="primary" @click="emit('search')">刷新图谱</el-button>
      </div>
    </header>

    <div class="knowledge-sphere-layout">
      <div
        ref="canvasHost"
        class="knowledge-sphere-stage"
        @pointerdown="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="handlePointerUp"
        @pointercancel="handlePointerCancel"
        @pointerleave="handlePointerLeave"
        @wheel="handleWheel"
      >
        <canvas ref="canvasRef" class="knowledge-sphere-canvas" />

        <div class="knowledge-sphere-overlay">
          <div class="knowledge-sphere-badge">
            <strong>RAG DAG</strong>
            <span>拖拽旋转，点击节点查看它的先修链和后续知识。</span>
          </div>

          <div v-if="hoveredNode" class="knowledge-sphere-tooltip" :style="tooltipStyle">
            <strong>{{ hoveredNode.label }}</strong>
            <span>{{ nodeSubtitle(hoveredNode) }}</span>
            <small v-if="hoveredNode.meta?.path">第 {{ hoveredNode.meta.path.order }} 步</small>
          </div>

          <div class="knowledge-sphere-actions">
            <button type="button" @click.stop="toggleRotation">
              {{ autoRotate ? '暂停旋转' : '恢复旋转' }}
            </button>
            <button type="button" :disabled="!activeSuggestion?.steps.length" @click.stop="playPath">
              播放路径
            </button>
            <button type="button" @click.stop="resetCamera">重置视角</button>
          </div>

          <div v-if="categoryChips.length" class="knowledge-sphere-categories">
            <button
              v-for="item in categoryChips"
              :key="item.key"
              type="button"
              :class="{ off: !activeCategories.has(item.key) }"
              @click.stop="toggleCategory(item.key)"
            >
              <i :style="{ background: item.color }" />
              <span>{{ item.label }}</span>
              <b>{{ item.count }}</b>
            </button>
          </div>
        </div>
      </div>

      <aside class="knowledge-sphere-sidebar">
        <div class="knowledge-sphere-card knowledge-sphere-current">
          <div class="knowledge-sphere-card-head">
            <strong>节点</strong>
            <button v-if="selectedNode" type="button" @click="clearSelection">清除</button>
          </div>
          <template v-if="selectedNode">
            <span>{{ nodeSubtitle(selectedNode) }}</span>
            <h3>{{ selectedNode.label }}</h3>
            <p>{{ selectedDescription }}</p>
            <div class="knowledge-sphere-meta">
              <small v-for="item in selectedFacts" :key="item.label">
                <b>{{ item.label }}</b>{{ item.value }}
              </small>
            </div>
            <div v-if="selectedEvidence.length" class="knowledge-sphere-evidence">
              <strong>证据</strong>
              <p v-for="item in selectedEvidence" :key="item">{{ item }}</p>
            </div>
            <div class="knowledge-sphere-relations">
              <section>
                <strong>先学</strong>
                <button
                  v-for="node in selectedPrerequisites"
                  :key="node.id"
                  type="button"
                  @click="selectNode(node.id, true)"
                >
                  {{ node.label }}
                </button>
                <span v-if="!selectedPrerequisites.length">无</span>
              </section>
              <section>
                <strong>后续</strong>
                <button
                  v-for="node in selectedNext"
                  :key="node.id"
                  type="button"
                  @click="selectNode(node.id, true)"
                >
                  {{ node.label }}
                </button>
                <span v-if="!selectedNext.length">无</span>
              </section>
            </div>
          </template>
          <template v-else>
            <span>点击任意节点，查看它在学习顺序中的位置。</span>
          </template>
        </div>

        <div class="knowledge-sphere-card">
          <div class="knowledge-sphere-card-head">
            <strong>学习路径</strong>
            <span>{{ activeSuggestion?.project_title || '全部知识库' }}</span>
          </div>
          <p v-if="activeSuggestion?.strategy" class="knowledge-sphere-strategy">
            {{ activeSuggestion.strategy }}
          </p>
          <div v-if="activeSuggestion?.dynamic_signals?.length" class="knowledge-sphere-signals">
            <small v-for="signal in activeSuggestion.dynamic_signals" :key="signal">{{ signal }}</small>
          </div>
          <ol v-if="activeSuggestion?.steps.length" class="knowledge-sphere-path">
            <li
              v-for="step in activeSuggestion.steps"
              :key="step.id"
              :class="{ active: selectedNode?.id === step.id }"
              @click="selectNode(step.id, true)"
            >
              <b>{{ step.order || '?' }}</b>
              <span>{{ step.label }}</span>
              <em>{{ step.phase || step.layer }} · {{ step.estimated_minutes || 35 }} 分钟</em>
              <small>{{ step.reason }}</small>
            </li>
          </ol>
          <span v-else>上传资料或建立项目知识点后，系统会重新计算路径。</span>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type {
  KnowledgeLinkEdge,
  KnowledgeLinkGraphResponse,
  KnowledgeLinkNode,
  KnowledgePathSuggestion
} from '../services/apiClient'

type ViewMode = 'all' | 'path' | 'evidence'
type Vec3 = {
  x: number
  y: number
  z: number
}
type WorldNode = Vec3 & {
  index: number
  node: KnowledgeLinkNode
  color: string
  rgb: [number, number, number]
  radius: number
  categoryKey: string
  appear: number
  countWeight: number
}
type WorldEdge = {
  index: number
  source: number
  target: number
  edge: KnowledgeLinkEdge
  path: boolean
}
type ProjectedNode = {
  sx: number
  sy: number
  pf: number
  radius: number
  visible: boolean
}
type CategoryChip = {
  key: string
  label: string
  color: string
  count: number
}

const props = defineProps<{
  graph: KnowledgeLinkGraphResponse | null
  loading?: boolean
  query: string
  projectId: number | null
  projectOptions: Array<{ id: number; title: string }>
  selectedNodeId?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:query', value: string): void
  (event: 'update:projectId', value: number | null): void
  (event: 'search'): void
  (event: 'select-node', node: KnowledgeLinkNode | null): void
}>()

const FOV = 1400
const WORLD_HEIGHT = 980
const SPIN_SPEED = 0.00018
const MAX_DRAW_EDGES = 900
const palette = ['#dc8b5e', '#2f7fa3', '#6f8f49', '#b99126', '#b76577', '#5f6fb0', '#a05a34', '#4f8b78']

const canvasHost = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const hoveredNode = ref<KnowledgeLinkNode | null>(null)
const selectedNode = ref<KnowledgeLinkNode | null>(null)
const tooltipStyle = ref<Record<string, string>>({})
const viewMode = ref<ViewMode>('all')
const autoRotate = ref(true)
const activeCategories = shallowRef<Set<string>>(new Set())
const categoryChips = ref<CategoryChip[]>([])

const viewOptions: Array<{ label: string; value: ViewMode }> = [
  { label: '全部', value: 'all' },
  { label: '路径', value: 'path' },
  { label: '证据', value: 'evidence' }
]

let context: CanvasRenderingContext2D | null = null
let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
let pathTimer = 0
let dpr = 1
let width = 0
let height = 0
let reduceMotion = false
let startedAt = 0
let lastFrameAt = 0
let grow = 0
let rotY = 0.58
let tilt = -0.32
let zoom = 1
let rotYTarget: number | null = null
let tiltTarget: number | null = null
let zoomTarget: number | null = null
let dragging = false
let moved = false
let lastPointerX = 0
let lastPointerY = 0
let pinchDistance = 0
let hoverIndex = -1

const pointers = new Map<number, [number, number]>()
const worldNodes: WorldNode[] = []
const projectedNodes: ProjectedNode[] = []
const worldEdges: WorldEdge[] = []
const nodeIndexById = new Map<string, number>()
const directPre = new Map<string, string[]>()
const directNext = new Map<string, string[]>()
let lineageNodes = new Set<string>()
let lineageEdges = new Set<number>()

const activeSuggestion = computed<KnowledgePathSuggestion | null>(() => {
  if (!props.graph?.path_suggestions.length) return null
  if (!props.projectId) return props.graph.path_suggestions[0]
  return props.graph.path_suggestions.find((item) => item.project_id === props.projectId) || props.graph.path_suggestions[0]
})

const pathNodeIds = computed(() => new Set((activeSuggestion.value?.steps || []).map((step) => step.id)))

const graphStats = computed(() => {
  const nodes = props.graph?.nodes.length || 0
  const edges = props.graph?.edges.length || 0
  const documents = props.graph?.meta?.document_count || 0
  const points = props.graph?.meta?.knowledge_point_count || 0
  return `${nodes} 节点 · ${edges} 关系 · ${documents} 资料 · ${points} 知识点`
})

const selectedDescription = computed(() => {
  if (!selectedNode.value) return ''
  const meta = selectedNode.value.meta || {}
  return (
    selectedNode.value.description ||
    String(meta.cluster_summary || '') ||
    String(meta.assessment_prompt || '') ||
    '暂无描述'
  )
})

const selectedEvidence = computed<string[]>(() => {
  const meta = selectedNode.value?.meta || {}
  const evidence = Array.isArray(meta.evidence) ? meta.evidence : []
  return evidence.map((item) => String(item)).filter(Boolean).slice(0, 3)
})

const selectedFacts = computed<Array<{ label: string; value: string }>>(() => {
  if (!selectedNode.value) return []
  const node = selectedNode.value
  const meta = node.meta || {}
  const facts: Array<{ label: string; value: string }> = []
  facts.push({ label: '分类', value: node.category || '知识点' })
  if (meta.chapter) facts.push({ label: '章节', value: formatMeta(meta.chapter) })
  if (meta.difficulty) facts.push({ label: '难度', value: formatMeta(meta.difficulty) })
  if (meta.chunk_count) facts.push({ label: '片段', value: formatMeta(meta.chunk_count) })
  if (meta.document_count) facts.push({ label: '资料', value: formatMeta(meta.document_count) })
  if (meta.dag_level !== undefined) facts.push({ label: '层级', value: formatMeta(meta.dag_level) })
  if (meta.degree !== undefined) facts.push({ label: '关系', value: `${formatMeta(meta.degree)} 条` })
  if (meta.path) {
    const path = meta.path as Record<string, unknown>
    facts.push({ label: '路径', value: `第 ${path.order || '?'} 步` })
  }
  return facts.slice(0, 8)
})

const selectedPrerequisites = computed(() => relatedNodes(selectedNode.value?.id || '', directPre))
const selectedNext = computed(() => relatedNodes(selectedNode.value?.id || '', directNext))

watch(
  () => props.graph,
  async () => {
    await nextTick()
    restartGrowth()
    rebuildWorldGraph()
  },
  { deep: true }
)

watch(
  () => props.selectedNodeId,
  (id) => {
    if (!id || !props.graph) {
      selectedNode.value = null
      buildLineage('')
      return
    }
    selectedNode.value = props.graph.nodes.find((item) => item.id === id) || null
    buildLineage(selectedNode.value?.id || '')
    if (selectedNode.value) focusNode(selectedNode.value.id)
  }
)

watch([viewMode, pathNodeIds], () => {
  rebuildWorldGraph()
})

onMounted(async () => {
  await nextTick()
  reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  context = canvasRef.value?.getContext('2d') || null
  resizeCanvas()
  rebuildWorldGraph()
  startedAt = performance.now()
  lastFrameAt = startedAt
  animationFrame = requestAnimationFrame(frame)
  resizeObserver = new ResizeObserver(() => resizeCanvas())
  if (canvasHost.value) resizeObserver.observe(canvasHost.value)
})

onBeforeUnmount(() => {
  if (animationFrame) cancelAnimationFrame(animationFrame)
  if (pathTimer) window.clearInterval(pathTimer)
  resizeObserver?.disconnect()
})

function updateProjectId(value: number | string | null | undefined) {
  emit('update:projectId', value === null || value === undefined || value === '' ? null : Number(value))
}

function updateQuery(value: string | number | null | undefined) {
  emit('update:query', String(value ?? ''))
}

function restartGrowth() {
  startedAt = performance.now()
  lastFrameAt = startedAt
  grow = reduceMotion ? 1 : 0
}

function rebuildWorldGraph() {
  worldNodes.length = 0
  projectedNodes.length = 0
  worldEdges.length = 0
  nodeIndexById.clear()
  directPre.clear()
  directNext.clear()

  const graph = props.graph
  if (!graph) {
    categoryChips.value = []
    return
  }

  const categories = buildCategoryChips(graph.nodes)
  categoryChips.value = categories
  syncActiveCategories(categories.map((item) => item.key))

  const levels = graph.nodes.map((node) => Math.max(0, Number(node.meta?.dag_level || 0)))
  const maxLevel = Math.max(1, ...levels)
  const layerLocalIndex = new Map<string, number>()
  const levelBuckets = buildLevelBuckets(graph.nodes)
  const isolatedNodes = graph.nodes.filter((node) => node.meta?.is_isolated)

  const ordered = [...graph.nodes].sort((left, right) => {
    const levelDelta = Number(left.meta?.dag_level || 0) - Number(right.meta?.dag_level || 0)
    if (levelDelta !== 0) return levelDelta
    return hashString(left.id) - hashString(right.id)
  })

  ordered.forEach((node) => {
    const key = `${node.layer}:${node.meta?.dag_level || 0}:${node.category || ''}`
    const index = layerLocalIndex.get(key) || 0
    layerLocalIndex.set(key, index + 1)
    const position = positionForNode(node, index, maxLevel, levelBuckets, isolatedNodes)
    const color = nodeColor(node)
    const worldNode: WorldNode = {
      index: worldNodes.length,
      node,
      color,
      rgb: hexToRgb(color),
      radius: nodeRadius(node),
      categoryKey: categoryKey(node),
      appear: Math.min(1, Math.max(0, position.y / WORLD_HEIGHT)),
      countWeight: Math.max(1, Number(node.weight || 1)),
      ...position
    }
    nodeIndexById.set(node.id, worldNode.index)
    worldNodes.push(worldNode)
    projectedNodes.push({ sx: 0, sy: 0, pf: 1, radius: worldNode.radius, visible: false })
  })

  graph.edges.slice(0, MAX_DRAW_EDGES).forEach((edge, index) => {
    const source = nodeIndexById.get(edge.source)
    const target = nodeIndexById.get(edge.target)
    if (source === undefined || target === undefined) return
    const path = pathNodeIds.value.has(edge.source) && pathNodeIds.value.has(edge.target)
    worldEdges.push({ index, source, target, edge, path })
    if (edge.relation === 'prerequisite') {
      pushRelation(directPre, edge.target, edge.source)
      pushRelation(directNext, edge.source, edge.target)
    }
  })

  buildLineage(selectedNode.value?.id || props.selectedNodeId || '')
}

function buildCategoryChips(nodes: KnowledgeLinkNode[]): CategoryChip[] {
  const counts = new Map<string, number>()
  nodes.forEach((node) => {
    const key = categoryKey(node)
    counts.set(key, (counts.get(key) || 0) + 1)
  })
  return Array.from(counts.entries())
    .map(([key, count]) => ({ key, label: categoryLabel(key), color: categoryColor(key), count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
    .slice(0, 10)
}

function buildLevelBuckets(nodes: KnowledgeLinkNode[]) {
  const buckets = new Map<number, KnowledgeLinkNode[]>()
  nodes.forEach((node) => {
    if (node.meta?.is_isolated) return
    const level = Math.max(0, Number(node.meta?.dag_level || 0))
    const list = buckets.get(level) || []
    list.push(node)
    buckets.set(level, list)
  })
  return buckets
}

function syncActiveCategories(keys: string[]) {
  const current = activeCategories.value
  if (!current.size) {
    activeCategories.value = new Set(keys)
    return
  }
  const next = new Set<string>()
  keys.forEach((key) => {
    if (current.has(key)) next.add(key)
  })
  activeCategories.value = next.size ? next : new Set(keys)
}

function toggleCategory(key: string) {
  const next = new Set(activeCategories.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  activeCategories.value = next
}

function positionForNode(
  node: KnowledgeLinkNode,
  index: number,
  maxLevel: number,
  levelBuckets: Map<number, KnowledgeLinkNode[]>,
  isolatedNodes: KnowledgeLinkNode[]
): Vec3 {
  if (node.meta?.is_isolated) return isolatedPosition(node, isolatedNodes)

  const path = node.meta?.path as Record<string, unknown> | undefined
  if (path?.order) return pathPosition(node, path)

  if (node.layer === 'document') return evidencePosition(node, index)
  if (node.layer === 'project') return targetPosition(node, index)

  const level = Math.max(0, Number(node.meta?.dag_level || 0))
  const yNorm = Math.min(0.9, Math.max(0.08, (level + 0.28) / (maxLevel + 1)))
  const y = yNorm * WORLD_HEIGHT
  const bucket = levelBuckets.get(level) || [node]
  const localIndex = Math.max(0, bucket.findIndex((item) => item.id === node.id))
  const count = Math.max(1, bucket.length)
  const baseAngle = (localIndex / count) * Math.PI * 2
  const categoryOffset = (hashString(categoryKey(node)) % 360) / 360 * Math.PI * 2
  const angle = baseAngle + categoryOffset * 0.33 + (hashString(node.id) % 17) * 0.018
  const funnelRadius = 72 + (1 - yNorm) * 438
  const jitter = (hashString(`${node.id}:r`) % 44) - 22
  const radius = funnelRadius + jitter
  return {
    x: Math.cos(angle) * radius,
    y,
    z: Math.sin(angle) * radius
  }
}

function pathPosition(node: KnowledgeLinkNode, path: Record<string, unknown>): Vec3 {
  const order = Math.max(1, Number(path.order || 1))
  const total = Math.max(1, activeSuggestion.value?.steps.length || 1)
  const t = total <= 1 ? 0.5 : (order - 1) / Math.max(1, total - 1)
  const y = (0.12 + t * 0.78) * WORLD_HEIGHT
  const angle = order * 1.22 + (hashString(node.id) % 19) * 0.03
  const radius = 28 + (order % 4) * 9 + (1 - t) * 88
  return {
    x: Math.cos(angle) * radius,
    y,
    z: Math.sin(angle) * radius
  }
}

function evidencePosition(node: KnowledgeLinkNode, index: number): Vec3 {
  const angle = index * 2.399 + (hashString(node.id) % 91) * 0.01
  const radius = 395 + (hashString(`${node.id}:doc`) % 78)
  return {
    x: Math.cos(angle) * radius,
    y: WORLD_HEIGHT * (0.04 + (index % 4) * 0.025),
    z: Math.sin(angle) * radius
  }
}

function targetPosition(node: KnowledgeLinkNode, index: number): Vec3 {
  const angle = index * 2.1 + 0.6
  const radius = 72 + (hashString(node.id) % 32)
  return {
    x: Math.cos(angle) * radius,
    y: WORLD_HEIGHT * 0.95,
    z: Math.sin(angle) * radius
  }
}

function isolatedPosition(node: KnowledgeLinkNode, isolatedNodes: KnowledgeLinkNode[]): Vec3 {
  const localIndex = Math.max(0, isolatedNodes.findIndex((item) => item.id === node.id))
  const angle = localIndex * 2.399963 + (hashString(node.id) % 37) * 0.04
  const ring = 96 + (localIndex % 5) * 26
  return {
    x: 600 + Math.cos(angle) * ring * 0.72,
    y: WORLD_HEIGHT * (0.18 + ((localIndex * 7) % 61) / 100),
    z: Math.sin(angle) * ring
  }
}

function frame(ts: number) {
  animationFrame = requestAnimationFrame(frame)
  if (!context) return

  if (!reduceMotion) grow = Math.min(1.02, ((ts - startedAt) / 2800) * 1.02)
  else grow = 1

  const dt = Math.min(64, ts - lastFrameAt)
  lastFrameAt = ts
  if (autoRotate.value && hoverIndex < 0 && !selectedNode.value && !dragging && !reduceMotion) {
    rotY += SPIN_SPEED * dt
  }
  updateCameraTween()
  draw()
}

function updateCameraTween() {
  if (rotYTarget === null) return
  const delta = normalizedAngle(rotYTarget - rotY)
  rotY += delta * 0.12
  if (tiltTarget !== null) tilt += (tiltTarget - tilt) * 0.12
  if (zoomTarget !== null) zoom += (zoomTarget - zoom) * 0.12
  if (Math.abs(delta) < 0.008) {
    rotYTarget = null
    tiltTarget = null
    zoomTarget = null
  }
}

function draw() {
  if (!context || !width || !height) return
  const ctx = context
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)
  drawBackground(ctx)
  projectNodes()
  drawFunnelGuides(ctx)
  drawEdges(ctx)
  drawNodes(ctx)
}

function drawBackground(ctx: CanvasRenderingContext2D) {
  const gradient = ctx.createLinearGradient(0, 0, width, height)
  gradient.addColorStop(0, '#fffdf9')
  gradient.addColorStop(0.58, '#ffffff')
  gradient.addColorStop(1, '#fff8ef')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, width, height)

  ctx.save()
  ctx.globalAlpha = 0.22
  ctx.strokeStyle = '#f0cebb'
  ctx.lineWidth = 1
  for (let x = 0; x < width; x += 42) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }
  for (let y = 0; y < height; y += 42) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }
  ctx.restore()
}

function drawFunnelGuides(ctx: CanvasRenderingContext2D) {
  if (!worldNodes.length) return
  ctx.save()
  ctx.lineWidth = 1
  const levels = [0.1, 0.32, 0.54, 0.76, 0.94]
  levels.forEach((level, index) => {
    const y = level * WORLD_HEIGHT
    const radius = 72 + (1 - level) * 438
    const points: Array<{ x: number; y: number }> = []
    for (let i = 0; i <= 96; i += 1) {
      const angle = (i / 96) * Math.PI * 2
      const projected = projectPoint({ x: Math.cos(angle) * radius, y, z: Math.sin(angle) * radius })
      points.push({ x: projected.sx, y: projected.sy })
    }
    ctx.strokeStyle = index === levels.length - 1 ? 'rgba(220,139,94,0.3)' : 'rgba(92,92,92,0.16)'
    ctx.beginPath()
    points.forEach((point, pointIndex) => {
      if (pointIndex === 0) ctx.moveTo(point.x, point.y)
      else ctx.lineTo(point.x, point.y)
    })
    ctx.stroke()
  })

  const axisStart = projectPoint({ x: 0, y: 0, z: 0 })
  const axisEnd = projectPoint({ x: 0, y: WORLD_HEIGHT, z: 0 })
  ctx.strokeStyle = 'rgba(220,139,94,0.22)'
  ctx.setLineDash([6, 8])
  ctx.beginPath()
  ctx.moveTo(axisStart.sx, axisStart.sy)
  ctx.lineTo(axisEnd.sx, axisEnd.sy)
  ctx.stroke()
  ctx.restore()
}

function drawEdges(ctx: CanvasRenderingContext2D) {
  const hasSelection = !!selectedNode.value
  const visibleEdges = worldEdges
    .filter((edge) => {
      const source = worldNodes[edge.source]
      const target = worldNodes[edge.target]
      return isNodeVisible(source) && isNodeVisible(target)
    })
    .sort((left, right) => {
      const leftDepth = projectedNodes[left.source].pf + projectedNodes[left.target].pf
      const rightDepth = projectedNodes[right.source].pf + projectedNodes[right.target].pf
      return leftDepth - rightDepth
    })

  ctx.save()
  visibleEdges.forEach((worldEdge) => {
    const source = projectedNodes[worldEdge.source]
    const target = projectedNodes[worldEdge.target]
    if (!source.visible || !target.visible) return

    const inLineage = lineageEdges.has(worldEdge.index)
    const sourceNode = worldNodes[worldEdge.source]
    const alpha = edgeAlpha(worldEdge, hasSelection, inLineage)
    if (alpha <= 0.01) return
    const rgb = inLineage ? sourceNode.rgb : edgeRgb(worldEdge.edge)
    const depth = Math.max(0.35, Math.min(1.15, (source.pf + target.pf) / 2))

    ctx.strokeStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha * depth})`
    ctx.lineWidth = inLineage || worldEdge.path ? 1.35 : worldEdge.edge.relation === 'prerequisite' ? 0.85 : 0.62
    ctx.beginPath()
    ctx.moveTo(source.sx, source.sy)
    ctx.lineTo(target.sx, target.sy)
    ctx.stroke()

    if (worldEdge.edge.relation === 'prerequisite' && (inLineage || worldEdge.path || viewMode.value !== 'evidence')) {
      drawArrow(ctx, source, target, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${Math.min(0.72, alpha * 1.25)})`)
    }
  })
  ctx.restore()
}

function drawNodes(ctx: CanvasRenderingContext2D) {
  const hasSelection = !!selectedNode.value
  const order = worldNodes
    .map((node) => node.index)
    .sort((left, right) => projectedNodes[left].pf - projectedNodes[right].pf)

  ctx.save()
  order.forEach((index) => {
    const worldNode = worldNodes[index]
    const projected = projectedNodes[index]
    if (!projected.visible || !isNodeVisible(worldNode)) return

    const node = worldNode.node
    const selected = selectedNode.value?.id === node.id
    const hovered = hoverIndex === index
    const lineage = lineageNodes.has(node.id)
    const path = pathNodeIds.value.has(node.id)
    let dim = 1
    if (hasSelection && !selected && !lineage && !path) dim = 0.14
    if (viewMode.value === 'path' && !path && !selected) dim *= node.layer === 'project' ? 0.35 : 0.22
    if (viewMode.value === 'evidence' && !['document', 'knowledge_base'].includes(node.layer) && !path) dim *= 0.22

    const r = projected.radius * (selected ? 1.55 : hovered ? 1.36 : path ? 1.18 : 1)
    const alpha = Math.min(1, dim * (0.62 + 0.38 * Math.min(1, projected.pf * projected.pf)))
    const [red, green, blue] = worldNode.rgb

    ctx.shadowBlur = 0
    ctx.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`
    ctx.beginPath()
    ctx.arc(projected.sx, projected.sy, r, 0, Math.PI * 2)
    ctx.fill()

    ctx.strokeStyle = selected || hovered || lineage || path ? '#172033' : `rgba(23, 32, 51, ${0.22 * dim})`
    ctx.lineWidth = selected || hovered ? 1.3 : lineage || path ? 0.95 : 0.55
    ctx.beginPath()
    ctx.arc(projected.sx, projected.sy, r, 0, Math.PI * 2)
    ctx.stroke()

    if (selected || hovered) {
      ctx.strokeStyle = selected ? '#dc8b5e' : '#172033'
      ctx.lineWidth = 1.15
      ctx.beginPath()
      ctx.arc(projected.sx, projected.sy, r + 2.8, 0, Math.PI * 2)
      ctx.stroke()
    }

    if (path) drawPathOrder(ctx, node, projected, r)
  })
  ctx.restore()
}

function drawPathOrder(ctx: CanvasRenderingContext2D, node: KnowledgeLinkNode, projected: ProjectedNode, radius: number) {
  const order = Number(node.meta?.path?.order || 0)
  if (!order) return
  const badgeRadius = Math.max(5.5, Math.min(8.5, radius * 0.72))
  const x = projected.sx + radius * 0.6
  const y = projected.sy - radius * 0.7
  ctx.fillStyle = '#172033'
  ctx.beginPath()
  ctx.arc(x, y, badgeRadius, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#ffffff'
  ctx.font = `700 ${Math.max(9, badgeRadius * 0.88)}px Inter, system-ui, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(String(order), x, y + 0.4)
}

function drawArrow(ctx: CanvasRenderingContext2D, source: ProjectedNode, target: ProjectedNode, color: string) {
  const dx = target.sx - source.sx
  const dy = target.sy - source.sy
  const length = Math.hypot(dx, dy)
  if (length < 12) return
  const ux = dx / length
  const uy = dy / length
  const endX = target.sx - ux * Math.max(8, target.radius * 1.15)
  const endY = target.sy - uy * Math.max(8, target.radius * 1.15)
  const size = Math.max(3.2, Math.min(5.2, target.radius * 0.78))
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.moveTo(endX, endY)
  ctx.lineTo(endX - ux * size - uy * size * 0.62, endY - uy * size + ux * size * 0.62)
  ctx.lineTo(endX - ux * size + uy * size * 0.62, endY - uy * size - ux * size * 0.62)
  ctx.closePath()
  ctx.fill()
}

function projectNodes() {
  worldNodes.forEach((node) => {
    const projected = projectPoint(node)
    const scaleBoost = Math.min(1.24, Math.max(0.8, zoom))
    const radius = (0.9 + Math.sqrt(node.countWeight) * node.radius * 0.22) * projected.pf * scaleBoost
    projectedNodes[node.index] = {
      sx: projected.sx,
      sy: projected.sy,
      pf: projected.pf,
      radius: Math.max(1.5, Math.min(5.2, radius)),
      visible: node.appear <= grow || reduceMotion
    }
  })
}

function projectPoint(point: Vec3) {
  const centeredY = point.y - WORLD_HEIGHT / 2
  const cosY = Math.cos(rotY)
  const sinY = Math.sin(rotY)
  const cosTilt = Math.cos(tilt)
  const sinTilt = Math.sin(tilt)
  const worldScale = Math.min(width / 1520, height / 1260) * zoom
  const centerX = width * 0.5
  const centerY = height * 0.53

  const x = point.x * cosY + point.z * sinY
  const z = -point.x * sinY + point.z * cosY
  const y2 = centeredY * cosTilt - z * sinTilt
  const z2 = centeredY * sinTilt + z * cosTilt
  const pf = FOV / (FOV + z2 * worldScale * 1.6)

  return {
    sx: centerX + x * worldScale * pf,
    sy: centerY - y2 * worldScale * pf,
    pf
  }
}

function isNodeVisible(worldNode: WorldNode) {
  if (!activeCategories.value.has(worldNode.categoryKey)) return false
  if (viewMode.value === 'path') return pathNodeIds.value.has(worldNode.node.id) || worldNode.node.layer === 'project' || lineageNodes.has(worldNode.node.id)
  if (viewMode.value === 'evidence') return ['document', 'knowledge_base'].includes(worldNode.node.layer) || pathNodeIds.value.has(worldNode.node.id)
  return true
}

function edgeAlpha(edge: WorldEdge, hasSelection: boolean, inLineage: boolean) {
  if (hasSelection) return inLineage ? 0.72 : edge.path ? 0.3 : 0.035
  if (edge.path) return 0.58
  if (edge.edge.relation === 'prerequisite') return edge.edge.strength === 'hard' ? 0.16 : 0.1
  if (edge.edge.relation === 'evidence') return 0.07
  return 0.08
}

function pickNode(x: number, y: number) {
  let best = -1
  let bestDistance = 18 * 18
  for (let index = 0; index < worldNodes.length; index += 1) {
    const node = worldNodes[index]
    const projected = projectedNodes[index]
    if (!projected.visible || !isNodeVisible(node)) continue
    const dx = projected.sx - x
    const dy = projected.sy - y
    const distance = dx * dx + dy * dy
    const threshold = Math.max(8, projected.radius + 6)
    if (distance < threshold * threshold && distance < bestDistance) {
      best = index
      bestDistance = distance
    }
  }
  return best
}

function handlePointerDown(event: PointerEvent) {
  if (!canvasHost.value) return
  if (event.target !== canvasRef.value) return
  pointers.set(event.pointerId, [event.clientX, event.clientY])
  canvasHost.value.setPointerCapture(event.pointerId)
  dragging = true
  moved = false
  lastPointerX = event.clientX
  lastPointerY = event.clientY
}

function handlePointerMove(event: PointerEvent) {
  if (!canvasHost.value) return
  if (event.target !== canvasRef.value && !pointers.has(event.pointerId)) return
  if (pointers.has(event.pointerId)) pointers.set(event.pointerId, [event.clientX, event.clientY])

  if (pointers.size === 2) {
    const [first, second] = Array.from(pointers.values())
    const distance = Math.hypot(first[0] - second[0], first[1] - second[1])
    if (pinchDistance) zoom = clamp(zoom * distance / pinchDistance, 0.54, 3.8)
    pinchDistance = distance
    dragging = false
    moved = true
    return
  }

  if (dragging) {
    const dx = event.clientX - lastPointerX
    const dy = event.clientY - lastPointerY
    if (Math.abs(dx) + Math.abs(dy) > 3) moved = true
    rotY += dx * 0.0055
    tilt = clamp(tilt - dy * 0.003, -1.08, 0.18)
    lastPointerX = event.clientX
    lastPointerY = event.clientY
    return
  }

  updateHover(event)
}

function handlePointerUp(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  pointers.delete(event.pointerId)
  if (pointers.size < 2) pinchDistance = 0
  if (!moved) selectFromPointer(event)
  dragging = false
}

function handlePointerCancel(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  pointers.delete(event.pointerId)
  dragging = false
  pinchDistance = 0
}

function handlePointerLeave() {
  dragging = false
  pointers.clear()
  pinchDistance = 0
  clearHover()
}

function handleWheel(event: WheelEvent) {
  if (event.target !== canvasRef.value) return
  event.preventDefault()
  zoom = clamp(zoom * Math.exp(-event.deltaY * 0.0015), 0.54, 3.8)
}

function updateHover(event: PointerEvent) {
  if (!canvasHost.value) return
  const rect = canvasHost.value.getBoundingClientRect()
  const index = pickNode(event.clientX - rect.left, event.clientY - rect.top)
  hoverIndex = index
  if (index < 0) {
    clearHover()
    return
  }
  hoveredNode.value = worldNodes[index].node
  tooltipStyle.value = placeTooltip(event.clientX - rect.left, event.clientY - rect.top)
  canvasHost.value.style.cursor = 'pointer'
}

function selectFromPointer(event: PointerEvent) {
  if (!canvasHost.value) return
  const rect = canvasHost.value.getBoundingClientRect()
  const index = pickNode(event.clientX - rect.left, event.clientY - rect.top)
  if (index < 0) {
    clearSelection()
    return
  }
  selectNode(worldNodes[index].node.id, true)
}

function placeTooltip(x: number, y: number) {
  const left = x > width - 280 ? x - 248 : x + 16
  const top = y > height - 150 ? y - 116 : y + 16
  return {
    left: `${Math.max(12, left)}px`,
    top: `${Math.max(12, top)}px`
  }
}

function clearHover() {
  hoverIndex = -1
  hoveredNode.value = null
  if (canvasHost.value) canvasHost.value.style.cursor = 'grab'
}

function clearSelection() {
  selectedNode.value = null
  emit('select-node', null)
  buildLineage('')
}

function selectNode(nodeId: string, shouldEmit: boolean) {
  const node = props.graph?.nodes.find((item) => item.id === nodeId) || null
  if (!node) return
  selectedNode.value = node
  buildLineage(node.id)
  focusNode(node.id)
  if (shouldEmit) emit('select-node', node)
}

function buildLineage(nodeId: string) {
  lineageNodes = new Set<string>()
  lineageEdges = new Set<number>()
  if (!nodeId) return
  const queue = [nodeId]
  lineageNodes.add(nodeId)
  while (queue.length) {
    const current = queue.shift()
    if (!current) continue
    for (const edge of worldEdges) {
      if (edge.edge.relation !== 'prerequisite') continue
      if (edge.edge.target !== current) continue
      lineageEdges.add(edge.index)
      if (!lineageNodes.has(edge.edge.source)) {
        lineageNodes.add(edge.edge.source)
        queue.push(edge.edge.source)
      }
    }
  }
}

function focusNode(nodeId: string) {
  const index = nodeIndexById.get(nodeId)
  if (index === undefined) return
  const node = worldNodes[index]
  let best = rotY
  let bestDepth = Infinity
  for (const candidate of [Math.atan2(-node.x, node.z), Math.atan2(-node.x, node.z) + Math.PI]) {
    const z = -node.x * Math.sin(candidate) + node.z * Math.cos(candidate)
    if (z < bestDepth) {
      bestDepth = z
      best = candidate
    }
  }
  rotYTarget = best
  tiltTarget = -0.2
  zoomTarget = Math.max(1.45, zoom)
}

function resetCamera() {
  rotYTarget = 0.58
  tiltTarget = -0.32
  zoomTarget = 1
}

function toggleRotation() {
  autoRotate.value = !autoRotate.value
}

function playPath() {
  const steps = activeSuggestion.value?.steps || []
  if (!steps.length) return
  if (pathTimer) window.clearInterval(pathTimer)
  viewMode.value = 'path'
  let index = 0
  selectNode(steps[index].id, true)
  pathTimer = window.setInterval(() => {
    index += 1
    if (index >= steps.length) {
      window.clearInterval(pathTimer)
      pathTimer = 0
      return
    }
    selectNode(steps[index].id, true)
  }, 1550)
}

function relatedNodes(nodeId: string, source: Map<string, string[]>) {
  const ids = source.get(nodeId) || []
  return ids
    .map((id) => props.graph?.nodes.find((node) => node.id === id) || null)
    .filter((node): node is KnowledgeLinkNode => Boolean(node))
    .slice(0, 8)
}

function pushRelation(map: Map<string, string[]>, key: string, value: string) {
  const list = map.get(key) || []
  if (!list.includes(value)) list.push(value)
  map.set(key, list)
}

function resizeCanvas() {
  const host = canvasHost.value
  const canvas = canvasRef.value
  if (!host || !canvas) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = Math.max(1, host.clientWidth)
  height = Math.max(1, host.clientHeight)
  canvas.width = Math.floor(width * dpr)
  canvas.height = Math.floor(height * dpr)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  context = canvas.getContext('2d')
}

function nodeRadius(node: KnowledgeLinkNode) {
  const weight = Math.max(1, Number(node.weight || 1))
  const pathBoost = pathNodeIds.value.has(node.id) ? 0.8 : 0
  if (node.layer === 'project') return 2.8 + pathBoost
  if (node.layer === 'document') return 1.8 + Math.min(1.1, Math.log(weight + 1) * 0.24)
  if (node.layer === 'platform') return 1.8 + pathBoost
  if (node.layer === 'knowledge_base') return 2.1 + Math.min(1.4, Math.log(weight + 1) * 0.28) + pathBoost
  return 1.7 + Math.min(1.2, Math.log(weight + 1) * 0.26)
}

function nodeColor(node: KnowledgeLinkNode) {
  if (pathNodeIds.value.has(node.id)) return '#dc8b5e'
  if (node.layer === 'project') return '#dc8b5e'
  if (node.layer === 'document') return '#b99126'
  if (node.layer === 'platform') return '#6f8f49'
  return categoryColor(categoryKey(node))
}

function categoryKey(node: KnowledgeLinkNode) {
  if (node.layer === 'platform') return '平台功能介绍'
  return String(node.category || node.meta?.subject || node.layer || '知识点')
}

function categoryLabel(key: string) {
  return key.replace(/^知识库[:：]/, '') || '知识点'
}

function categoryColor(key: string) {
  if (key === '平台功能介绍') return '#6f8f49'
  if (key.includes('文献') || key.includes('论文')) return '#2f7fa3'
  if (key.includes('项目')) return '#dc8b5e'
  if (key.includes('资料') || key.includes('pdf') || key.includes('document')) return '#b99126'
  return palette[hashString(key) % palette.length]
}

function edgeRgb(edge: KnowledgeLinkEdge): [number, number, number] {
  if (edge.relation === 'prerequisite') return edge.strength === 'hard' ? [154, 85, 43] : [104, 104, 104]
  if (edge.relation === 'evidence') return [93, 121, 141]
  return [103, 127, 74]
}

function nodeSubtitle(node: KnowledgeLinkNode) {
  if (node.layer === 'project') return `项目 · ${node.category || '学习目标'}`
  if (node.layer === 'document') return `资料 · ${node.category || 'document'}`
  if (node.layer === 'platform') return '平台功能介绍'
  if (node.layer === 'knowledge_base') return `知识点 · ${node.category || '知识库'}`
  const meta = node.meta || {}
  const age = formatAge(meta.age_range)
  return `${meta.subject || '知识'} · ${meta.domain || node.category || 'domain'}${age ? ` · ${age}` : ''}`
}

function formatAge(value: unknown): string {
  if (!Array.isArray(value)) return ''
  const [start, end] = value
  if (!start && !end) return ''
  return `${start || '?'}-${end || '?'} 岁`
}

function formatMeta(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).slice(0, 4).join(' / ')
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  if (typeof value === 'object' && value) {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== null && item !== undefined && item !== '')
      .map(([key, item]) => `${key.replace(/_/g, ' ')}: ${formatMeta(item)}`)
      .slice(0, 4)
      .join(' / ')
  }
  return String(value)
}

function hexToRgb(color: string): [number, number, number] {
  const value = color.replace('#', '')
  const numeric = Number.parseInt(value.length === 3 ? value.split('').map((char) => char + char).join('') : value, 16)
  return [(numeric >> 16) & 255, (numeric >> 8) & 255, numeric & 255]
}

function hashString(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function normalizedAngle(value: number) {
  return ((value + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI
}
</script>

<style scoped>
.knowledge-sphere-panel {
  display: grid;
  gap: 16px;
  grid-column: 1 / -1;
}

.knowledge-sphere-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
}

.knowledge-sphere-toolbar__title {
  display: grid;
  gap: 4px;
}

.knowledge-sphere-toolbar__title strong {
  color: var(--study-ink);
  font-size: 28px;
  letter-spacing: 0;
}

.knowledge-sphere-toolbar__title span {
  color: var(--study-muted);
  font-size: 12px;
}

.knowledge-sphere-toolbar__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.knowledge-sphere-select {
  width: 190px;
}

.knowledge-sphere-search {
  width: min(380px, 42vw);
}

.knowledge-sphere-segments {
  display: inline-flex;
  padding: 3px;
  border: 1px solid rgba(220, 139, 94, 0.2);
  border-radius: 8px;
  background: #ffefd6;
}

.knowledge-sphere-segments button,
.knowledge-sphere-actions button,
.knowledge-sphere-categories button,
.knowledge-sphere-card-head button,
.knowledge-sphere-relations button {
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #596273;
  cursor: pointer;
  font-size: 12px;
  transition: background 180ms ease, color 180ms ease, transform 180ms ease;
}

.knowledge-sphere-segments button {
  padding: 7px 10px;
}

.knowledge-sphere-segments button.active {
  background: #dc8b5e;
  color: #fff;
}

.knowledge-sphere-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.92fr) minmax(330px, 0.72fr);
  gap: 16px;
}

.knowledge-sphere-stage {
  position: relative;
  min-height: 760px;
  border: 1px solid rgba(220, 139, 94, 0.16);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 20px 54px rgba(60, 48, 42, 0.1);
  cursor: grab;
  touch-action: none;
}

.knowledge-sphere-stage:active {
  cursor: grabbing;
}

.knowledge-sphere-canvas {
  position: absolute;
  inset: 0;
  display: block;
}

.knowledge-sphere-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.knowledge-sphere-badge,
.knowledge-sphere-actions,
.knowledge-sphere-tooltip,
.knowledge-sphere-categories {
  border: 1px solid rgba(70, 74, 82, 0.12);
  background: rgba(255, 253, 249, 0.9);
  box-shadow: 0 12px 28px rgba(58, 54, 49, 0.1);
  backdrop-filter: blur(14px);
}

.knowledge-sphere-badge {
  position: absolute;
  top: 16px;
  left: 16px;
  display: grid;
  max-width: 300px;
  gap: 5px;
  padding: 12px 14px;
  border-radius: 8px;
  color: #172033;
  font-size: 12px;
}

.knowledge-sphere-badge strong {
  font-size: 15px;
}

.knowledge-sphere-badge span {
  color: #6d6472;
  line-height: 1.5;
}

.knowledge-sphere-tooltip {
  position: absolute;
  z-index: 4;
  display: grid;
  width: 238px;
  gap: 3px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #172033;
}

.knowledge-sphere-tooltip strong,
.knowledge-sphere-tooltip span,
.knowledge-sphere-tooltip small {
  display: block;
}

.knowledge-sphere-tooltip span,
.knowledge-sphere-tooltip small {
  color: #6d6472;
  font-size: 12px;
}

.knowledge-sphere-actions {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  gap: 6px;
  padding: 5px;
  border-radius: 8px;
  pointer-events: auto;
}

.knowledge-sphere-actions button {
  padding: 7px 9px;
}

.knowledge-sphere-actions button:hover,
.knowledge-sphere-categories button:hover,
.knowledge-sphere-card-head button:hover,
.knowledge-sphere-relations button:hover {
  background: rgba(220, 139, 94, 0.12);
  color: #172033;
  transform: translateY(-1px);
}

.knowledge-sphere-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.knowledge-sphere-categories {
  position: absolute;
  right: 16px;
  bottom: 16px;
  left: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 9px;
  border-radius: 8px;
  pointer-events: auto;
}

.knowledge-sphere-categories button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.76);
  color: #383c44;
}

.knowledge-sphere-categories button.off {
  opacity: 0.42;
}

.knowledge-sphere-categories i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  box-shadow: 0 0 0 1px rgba(23, 32, 51, 0.16);
}

.knowledge-sphere-categories b {
  color: #8d4d2f;
  font-variant-numeric: tabular-nums;
}

.knowledge-sphere-sidebar {
  display: grid;
  gap: 14px;
  align-content: start;
}

.knowledge-sphere-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid rgba(220, 139, 94, 0.16);
  border-radius: 8px;
  background: #ffefd6;
}

.knowledge-sphere-card strong {
  color: var(--study-ink);
}

.knowledge-sphere-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-sphere-card-head button {
  padding: 5px 8px;
}

.knowledge-sphere-card-head span,
.knowledge-sphere-current > span,
.knowledge-sphere-card > span {
  color: var(--study-muted);
  font-size: 12px;
}

.knowledge-sphere-card h3 {
  margin: 0;
  color: var(--study-ink);
  font-size: 18px;
  line-height: 1.3;
  text-wrap: balance;
}

.knowledge-sphere-card p {
  margin: 0;
  color: var(--study-soft);
  line-height: 1.65;
}

.knowledge-sphere-meta,
.knowledge-sphere-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.knowledge-sphere-meta small,
.knowledge-sphere-signals small {
  display: inline-flex;
  gap: 5px;
  padding: 6px 8px;
  border-radius: 8px;
  background: #f0cebb;
  color: #4c4139;
}

.knowledge-sphere-meta b {
  color: #8d4d2f;
}

.knowledge-sphere-evidence {
  display: grid;
  gap: 6px;
  padding-top: 4px;
}

.knowledge-sphere-evidence strong {
  font-size: 13px;
}

.knowledge-sphere-evidence p {
  padding-left: 10px;
  border-left: 2px solid #dc8b5e;
  font-size: 13px;
}

.knowledge-sphere-relations {
  display: grid;
  gap: 8px;
}

.knowledge-sphere-relations section {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
}

.knowledge-sphere-relations strong {
  width: 42px;
  font-size: 13px;
}

.knowledge-sphere-relations button,
.knowledge-sphere-relations span {
  padding: 6px 8px;
  border-radius: 8px;
  background: color-mix(in srgb, #ffffff 60%, #c4daeb);
  color: #4c4139;
  font-size: 12px;
}

.knowledge-sphere-strategy {
  font-size: 13px;
}

.knowledge-sphere-path {
  max-height: 430px;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  overflow: auto;
  list-style: none;
}

.knowledge-sphere-path li {
  position: relative;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 2px 10px;
  padding: 10px;
  border-radius: 8px;
  background: color-mix(in srgb, #ffefd6 74%, #ffffff);
  cursor: pointer;
  transition: transform 160ms ease, background 160ms ease, box-shadow 160ms ease;
}

.knowledge-sphere-path li:hover,
.knowledge-sphere-path li.active {
  background: #fadfa7;
  box-shadow: 0 10px 24px rgba(220, 139, 94, 0.12);
  transform: translateY(-1px);
}

.knowledge-sphere-path b {
  grid-row: 1 / span 3;
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 8px;
  background: #dc8b5e;
  color: #fff;
  font-size: 12px;
}

.knowledge-sphere-path span {
  min-width: 0;
  color: var(--study-ink);
  font-weight: 650;
}

.knowledge-sphere-path em {
  color: #8d4d2f;
  font-size: 12px;
  font-style: normal;
}

.knowledge-sphere-path small {
  color: var(--study-muted);
  line-height: 1.45;
}

@media (max-width: 1180px) {
  .knowledge-sphere-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .knowledge-sphere-stage {
    min-height: 620px;
  }
}

@media (max-width: 720px) {
  .knowledge-sphere-toolbar__controls,
  .knowledge-sphere-search,
  .knowledge-sphere-select {
    width: 100%;
  }

  .knowledge-sphere-stage {
    min-height: 560px;
  }

  .knowledge-sphere-actions {
    top: auto;
    right: 12px;
    bottom: 92px;
  }

  .knowledge-sphere-badge {
    right: 12px;
    max-width: none;
  }

  .knowledge-sphere-categories {
    max-height: 78px;
    overflow: auto;
  }
}
</style>
