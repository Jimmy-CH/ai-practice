<template>
  <section class="panel">
    <div class="panel-header">
      <span>产物</span>
      <div v-if="hasArtifacts" class="toolbar">
        <span class="tiny muted">口径</span>
        <el-radio-group v-model="toneModel" size="small">
          <el-radio-button value="business">业务</el-radio-button>
          <el-radio-button value="tech">技术</el-radio-button>
        </el-radio-group>
        <span class="tiny muted">脱敏</span>
        <el-switch v-model="maskModel" size="small" />
      </div>
    </div>

    <template v-if="hasArtifacts">
      <div class="tabs">
        <div v-for="t in tabs" :key="t.kind" class="tab"
             :class="{ 'tab--active': activeKind === t.kind }" @click="activeKind = t.kind">
          {{ t.label }}
        </div>
        <div class="tab-actions">
          <el-button size="small" @click="copyContent">复制</el-button>
          <el-button size="small" type="primary" plain @click="download">下载</el-button>
        </div>
      </div>
      <div class="panel-body scroll output-body">
        <div v-if="loadError" class="note-box output-error">{{ loadError }}</div>
        <div v-else-if="loading" class="empty">加载产物中…</div>
        <template v-else>
          <table v-if="activeKind === 'checklist'" class="table-simple">
            <thead>
              <tr><th v-for="(h, i) in csvHead" :key="i">{{ h }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in csvBody" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="activeKind === 'document'" ref="mdHost" class="md-view" v-html="mdHtml" />
          <pre v-else class="json-view">{{ jsonText }}</pre>
        </template>
      </div>
    </template>
    <div v-else class="panel-body empty">运行完成后在此查看三类产物并导出</div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { artifactDownloadUrl, extractError, getArtifactText } from '@/api/client'
import { formatJson, parseCsv, renderMarkdown } from '@/render/artifacts'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

const tabs = [
  { kind: 'checklist', label: '发布检查清单' },
  { kind: 'document', label: '产品说明' },
  { kind: 'trace', label: '溯源数据' },
]

const activeKind = ref('checklist')
const content = ref('')
const loading = ref(false)
const loadError = ref('')
const mdHost = ref<HTMLElement | null>(null)

const hasArtifacts = computed(() => !!runStore.current?.artifacts?.length)

const toneModel = computed({
  get: () => store.tone,
  set: (v: string | number | boolean | undefined) => { store.tone = v === 'tech' ? 'tech' : 'business' },
})
const maskModel = computed({
  get: () => store.mask,
  set: (v: string | number | boolean) => { store.mask = Boolean(v) },
})

const csvRows = computed(() => (activeKind.value === 'checklist' && content.value ? parseCsv(content.value) : []))
const csvHead = computed(() => csvRows.value[0] || [])
const csvBody = computed(() => csvRows.value.slice(1))
const mdHtml = computed(() => (activeKind.value === 'document' && content.value ? renderMarkdown(content.value) : ''))
const jsonText = computed(() => (activeKind.value === 'trace' && content.value ? formatJson(content.value) : ''))

// 产物加载时序守卫：口径/运行快速连点时丢弃过期响应，防旧内容覆盖新渲染
let loadSeq = 0

async function load() {
  const run = runStore.current
  const seq = ++loadSeq
  if (!run || !run.artifacts?.length) {
    content.value = ''
    loadError.value = ''
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const text = await getArtifactText(run.id, activeKind.value, store.tone, store.mask)
    if (seq !== loadSeq) return   // 已有更新的加载请求，丢弃过期响应
    content.value = text
  } catch (err) {
    if (seq !== loadSeq) return
    content.value = ''
    loadError.value = extractError(err)
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

watch(
  () => [runStore.current?.id, runStore.result, activeKind.value, store.tone, store.mask],
  () => { void load() },
  { immediate: true },
)

// mermaid 动态加载并逐块绘制：单图语法错误只降级该图为代码块，不影响整篇文档
let mermaidSeq = 0

function degradeMermaid(node: HTMLElement, source: string) {
  const pre = document.createElement('pre')
  pre.className = 'mermaid-fallback'
  pre.textContent = source
  node.replaceWith(pre)
}

async function paintMermaid() {
  const seq = ++mermaidSeq
  const host = mdHost.value
  if (!host) return
  const blocks = Array.from(host.querySelectorAll<HTMLElement>('.mermaid:not([data-processed])'))
  if (!blocks.length) return
  const sources = new Map(blocks.map((node) => [node, node.textContent || '']))
  const { default: mermaid } = await import('mermaid')
  if (seq !== mermaidSeq) return   // 已切换产物或重新加载，丢弃过期渲染
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral' })
  const drawable: HTMLElement[] = []
  for (const node of blocks) {
    try {
      await mermaid.parse(sources.get(node) || '')
      drawable.push(node)
    } catch {
      degradeMermaid(node, sources.get(node) || '')
    }
  }
  if (!drawable.length) return
  try {
    await mermaid.run({ nodes: drawable })
  } catch {
    // 逐块兜底在下方统一处理，避免一块异常中断全部图形
  }
  for (const node of drawable) {
    if (!node.isConnected || node.querySelector('svg')) continue
    degradeMermaid(node, sources.get(node) || '')
  }
}

watch([mdHtml, loading], () => { void nextTick(paintMermaid) }, { flush: 'post' })

async function copyContent() {
  if (!content.value) return
  try {
    await navigator.clipboard.writeText(content.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

function download() {
  const run = runStore.current
  if (!run) return
  window.open(artifactDownloadUrl(run.id, activeKind.value, store.tone, store.mask), '_blank')
}
</script>

<style scoped>
.output-body { max-height: calc(100vh - 300px); }
.tiny { font-size: 12px; }
.tab-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.output-error { background: #fdf3f3; border-color: #f5c6c8; color: #a03034; }
.output-body :deep(.table-simple) { white-space: nowrap; }
.md-view :deep(.mermaid) { margin: 8px 0; overflow-x: auto; text-align: center; }
.md-view :deep(.mermaid svg) { max-width: 100%; height: auto; }
.md-view :deep(.mermaid-fallback) { background: #fdf3f3; border: 1px solid #f5c6c8;
  border-radius: 6px; color: #a03034; overflow-x: auto; padding: 8px 10px; }
</style>
