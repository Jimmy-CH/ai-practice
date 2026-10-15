<template>
  <div class="steps">
    <div v-for="s in displaySteps" :key="s.index" class="step" :class="stepClass(s)">
      <div class="step-title">
        <span class="step-no">{{ s.index + 1 }}</span>
        <span>{{ s.name }}</span>
        <span class="step-side" :class="`step-side--${s.status}`">{{ statusText(s) }}</span>
      </div>
      <div class="step-meta">
        <div><em>读</em>{{ explain(s.index).read }}</div>
        <div><em>写</em>{{ explain(s.index).write }}</div>
        <div><em>失败</em>{{ explain(s.index).failure }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StepState } from '@/types'
import { STEP_EXPLAINS, STEP_NAMES, type StepExplain } from '@/data/steps'

const props = defineProps<{ steps: StepState[] }>()

const displaySteps = computed<StepState[]>(() => {
  if (props.steps.length) return props.steps
  return STEP_NAMES.map((name, index) => ({ index, name, status: 'pending' as const }))
})

function stepClass(s: StepState): string {
  return s.status === 'pending' ? '' : `step--${s.status}`
}

function statusText(s: StepState): string {
  if (s.status === 'active') return '运行中…'
  if (s.status === 'done') return `已完成${durationText(s)}`
  if (s.status === 'failed') return '失败'
  return '待运行'
}

function durationText(s: StepState): string {
  if (s.duration_ms === undefined || s.duration_ms === null) return ''
  return s.duration_ms >= 1000 ? ` · ${(s.duration_ms / 1000).toFixed(1)}s` : ` · ${s.duration_ms}ms`
}

function explain(index: number): StepExplain {
  return STEP_EXPLAINS[index] || { read: '', write: '', failure: '' }
}
</script>

<style scoped>
.step-side { margin-left: auto; font-size: 12px; color: var(--muted); white-space: nowrap; }
.step-side--active { color: var(--brand); }
.step-side--done { color: var(--ok); }
.step-side--failed { color: var(--danger); }
.step-meta div { word-break: break-all; }
</style>
