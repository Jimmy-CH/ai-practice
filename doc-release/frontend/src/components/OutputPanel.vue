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
          <div v-else-if="activeKind === 'document'" class="md-view" v-html="mdHtml" />
          <pre v-else class="json-view">{{ jsonText }}</pre>
        </template>
      </div>
    </template>
    <div v-else class="panel-body empty">运行完成后在此查看三类产物并导出</div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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

async function load() {
  const run = runStore.current
  if (!run || !run.artifacts?.length) {
    content.value = ''
    loadError.value = ''
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    content.value = await getArtifactText(run.id, activeKind.value, store.tone, store.mask)
  } catch (err) {
    content.value = ''
    loadError.value = extractError(err)
  } finally {
    loading.value = false
  }
}

watch(
  () => [runStore.current?.id, runStore.result, activeKind.value, store.tone, store.mask],
  () => { void load() },
  { immediate: true },
)

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
</style>
