import katex from 'katex'

type MathSegment = {
  raw: string
  body: string
  displayMode: boolean
  start: number
  end: number
}

const SKIP_TAGS = new Set([
  'SCRIPT',
  'STYLE',
  'TEXTAREA',
  'INPUT',
  'SELECT',
  'OPTION',
  'PRE',
  'CODE',
  'KBD',
  'SAMP',
  'CANVAS',
  'SVG'
])

let observer: MutationObserver | null = null
let scheduled = 0

export function startGlobalMathRendering(root: ParentNode = document.body) {
  renderMathInElement(root)
  observer?.disconnect()
  observer = new MutationObserver(() => {
    window.clearTimeout(scheduled)
    scheduled = window.setTimeout(() => renderMathInElement(root), 80)
  })
  observer.observe(root, {
    childList: true,
    characterData: true,
    subtree: true
  })
}

export function stopGlobalMathRendering() {
  observer?.disconnect()
  observer = null
  window.clearTimeout(scheduled)
}

export function renderMathInElement(root: ParentNode) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.textContent || !hasMathDelimiter(node.textContent)) return NodeFilter.FILTER_REJECT
      const parent = node.parentElement
      if (!parent || shouldSkipElement(parent)) return NodeFilter.FILTER_REJECT
      return NodeFilter.FILTER_ACCEPT
    }
  })
  const nodes: Text[] = []
  while (walker.nextNode()) nodes.push(walker.currentNode as Text)
  nodes.forEach(renderMathTextNode)
}

function renderMathTextNode(node: Text) {
  const text = node.textContent || ''
  const segments = extractMathSegments(text)
  if (!segments.length) return

  const fragment = document.createDocumentFragment()
  let cursor = 0
  for (const segment of segments) {
    if (segment.start > cursor) {
      fragment.append(document.createTextNode(text.slice(cursor, segment.start)))
    }
    fragment.append(renderFormulaNode(segment))
    cursor = segment.end
  }
  if (cursor < text.length) fragment.append(document.createTextNode(text.slice(cursor)))
  node.replaceWith(fragment)
}

function renderFormulaNode(segment: MathSegment) {
  const wrapper = document.createElement('span')
  wrapper.className = segment.displayMode ? 'tex-formula tex-formula-block' : 'tex-formula tex-formula-inline'
  wrapper.dataset.mathRendered = 'true'
  try {
    wrapper.innerHTML = katex.renderToString(segment.body, {
      displayMode: segment.displayMode,
      throwOnError: false,
      strict: 'ignore',
      output: 'htmlAndMathml',
      trust: false
    })
  } catch {
    wrapper.textContent = segment.raw
    wrapper.classList.add('tex-formula-error')
  }
  return wrapper
}

function extractMathSegments(text: string): MathSegment[] {
  const segments: MathSegment[] = []
  let index = 0
  while (index < text.length) {
    const next = findNextDelimiter(text, index)
    if (!next) break
    const close = text.indexOf(next.close, next.bodyStart)
    if (close < 0) break
    const body = text.slice(next.bodyStart, close).trim()
    const end = close + next.close.length
    if (body && isLikelyFormula(body, next.open)) {
      segments.push({
        raw: text.slice(next.start, end),
        body,
        displayMode: next.displayMode,
        start: next.start,
        end
      })
    }
    index = Math.max(end, next.start + next.open.length)
  }
  return segments
}

function findNextDelimiter(text: string, from: number) {
  const candidates = [
    { open: '$$', close: '$$', displayMode: true },
    { open: '\\[', close: '\\]', displayMode: true },
    { open: '\\(', close: '\\)', displayMode: false },
    { open: '$', close: '$', displayMode: false }
  ]
    .map((candidate) => {
      const start = text.indexOf(candidate.open, from)
      return start >= 0 ? { ...candidate, start, bodyStart: start + candidate.open.length } : null
    })
    .filter((candidate): candidate is NonNullable<typeof candidate> => Boolean(candidate))
    .sort((left, right) => left.start - right.start || right.open.length - left.open.length)
  return candidates[0] || null
}

function hasMathDelimiter(text: string) {
  return text.includes('\\(') || text.includes('\\[') || text.includes('$$') || text.includes('$')
}

function isLikelyFormula(body: string, delimiter: string) {
  if (delimiter !== '$') return true
  if (body.length > 160) return false
  if (/^\d+(?:[.,]\d+)?$/.test(body)) return false
  return /[\\_^=+\-*/<>]|[A-Za-z]/.test(body)
}

function shouldSkipElement(element: Element): boolean {
  if (SKIP_TAGS.has(element.tagName)) return true
  return Boolean(element.closest('.katex, .tex-formula, [data-math-rendered="true"], [contenteditable="true"]'))
}
