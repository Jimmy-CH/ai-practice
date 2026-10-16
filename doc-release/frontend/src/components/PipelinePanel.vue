<template>
  <section class="panel">
    <div class="panel-header">
      <span>运行流水线</span>
      <StatusBadge v-if="runStore.status !== 'idle'" :status="runStore.status" />
    </div>
    <div class="pipeline-body">
      <StepList :steps="runStore.steps" />
      <TerminalLog :logs="runStore.logs" />
    </div>
    <div v-if="runStore.error" class="note-box pipeline-error">{{ runStore.error }}</div>
  </section>
</template>

<script setup lang="ts">
import { useRunStore } from '@/stores/run'
import StatusBadge from '@/components/StatusBadge.vue'
import StepList from '@/components/StepList.vue'
import TerminalLog from '@/components/TerminalLog.vue'

const runStore = useRunStore()
</script>

<style scoped>
.pipeline-body { display: flex; flex-direction: column; gap: 12px; padding: 14px; }
.pipeline-error { margin: 0 14px 14px; background: #fdf3f3; border-color: #f5c6c8; color: #a03034; }
</style>
