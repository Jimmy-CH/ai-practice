<template>
  <div class="console">
    <ControlBar />
    <div class="console-grid">
      <DiffPanel />
      <PipelinePanel />
      <OutputPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import ControlBar from '@/components/ControlBar.vue'
import DiffPanel from '@/components/DiffPanel.vue'
import OutputPanel from '@/components/OutputPanel.vue'
import PipelinePanel from '@/components/PipelinePanel.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

onMounted(async () => {
  await store.loadRepos()
  // 刷新页面后恢复现场：优先恢复最近一次运行
  if (!runStore.current) {
    const lastRun = localStorage.getItem('docrelease:lastRun')
    if (lastRun) {
      try {
        await runStore.attach(lastRun)
        if (runStore.current) {
          // 用运行参数还原控制条与变更预览，避免恢复后控制条与产物不一致
          await store.alignToRun(runStore.current)
        }
      } catch {
        localStorage.removeItem('docrelease:lastRun')
      }
    }
  }
  // 从其他页面切回时，若当前运行仍在进行且流已断开，则重新订阅
  if (runStore.current && runStore.isActive && !runStore.handle) {
    runStore.connect(runStore.current.id)
  }
})

onBeforeUnmount(() => {
  runStore.closeStream()
})
</script>

<style scoped>
.console { display: flex; flex-direction: column; gap: 14px; }
.console-grid { display: grid; grid-template-columns: 1.05fr 0.85fr 1.1fr; gap: 14px; align-items: start; }
@media (max-width: 1180px) {
  .console-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 820px) {
  .console-grid { grid-template-columns: 1fr; }
}
</style>
