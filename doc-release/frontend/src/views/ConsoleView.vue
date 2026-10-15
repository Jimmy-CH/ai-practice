<template>
  <div class="console">
    <ControlBar />
    <div class="console-grid">
      <DiffPanel />
      <PipelinePanel />
      <section class="panel">
        <div class="panel-header"><span>产物</span></div>
        <div class="panel-body empty">产物面板接入中</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import ControlBar from '@/components/ControlBar.vue'
import DiffPanel from '@/components/DiffPanel.vue'
import PipelinePanel from '@/components/PipelinePanel.vue'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

onMounted(async () => {
  await store.loadRepos()
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
