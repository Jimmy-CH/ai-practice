<template>
  <div class="detail">
    <section class="panel">
      <div class="panel-header">
        <div class="toolbar">
          <el-button size="small" @click="router.push('/history')">← 返回列表</el-button>
          <span class="mono muted">{{ runId }}</span>
        </div>
        <StatusBadge v-if="runStore.current" :status="runStore.status" />
      </div>
      <div v-if="runStore.current" class="panel-body detail-meta">
        <div class="meta-item"><span class="muted">仓库</span><b>{{ runStore.current.repo_name }}</b></div>
        <div class="meta-item"><span class="muted">版本</span><b>{{ runStore.current.version_label }}</b></div>
        <div class="meta-item"><span class="muted">范围</span><b class="mono">{{ runStore.current.base_ref }}..{{ runStore.current.head_ref }}</b></div>
        <div class="meta-item"><span class="muted">开始</span><b class="mono">{{ formatDateTime(runStore.current.created_at) }}</b></div>
        <div class="meta-item"><span class="muted">结束</span><b class="mono">{{ formatDateTime(runStore.current.finished_at) }}</b></div>
      </div>
      <div v-else class="panel-body empty">加载运行详情中…</div>
    </section>
    <div class="detail-grid">
      <PipelinePanel />
      <OutputPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { extractError } from '@/api/client'
import OutputPanel from '@/components/OutputPanel.vue'
import PipelinePanel from '@/components/PipelinePanel.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'
import { formatDateTime } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
const runStore = useRunStore()
const repoStore = useRepoStore()

const runId = computed(() => String(route.params.id || ''))

onMounted(async () => {
  try {
    await runStore.attach(runId.value)
    const run = runStore.current
    if (run) {
      repoStore.tone = run.tone === 'tech' ? 'tech' : 'business'
      repoStore.mask = run.mask
    }
  } catch (err) {
    ElMessage.error(extractError(err))
    void router.replace('/history')
  }
})

onBeforeUnmount(() => {
  runStore.closeStream()
})
</script>

<style scoped>
.detail { display: flex; flex-direction: column; gap: 14px; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 10px 26px; }
.meta-item { display: flex; gap: 8px; align-items: baseline; font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: 0.9fr 1.1fr; gap: 14px; align-items: start; }
@media (max-width: 980px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
