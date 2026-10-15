<template>
  <div class="term">
    <div class="term-hd">
      <span class="dots"><i></i><i></i><i></i></span>
      <span>docrelease — /workspace/pipeline</span>
    </div>
    <div ref="box" class="term-body">
      <div v-if="!logs.length" class="term-hint">等待运行日志…</div>
      <div v-for="(l, i) in logs" :key="i" class="term-line" :class="lineClass(l)">
        <span class="term-ts">{{ timeOf(l.ts) }}</span>
        <span class="term-tag">{{ l.tag }}</span>
        <span>{{ l.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { LogLine } from '@/types'

const props = defineProps<{ logs: LogLine[] }>()
const box = ref<HTMLElement | null>(null)

function timeOf(ts: string): string {
  return ts.length >= 19 ? ts.slice(11, 19) : ts
}

function lineClass(l: LogLine): string {
  if (l.channel === 'error') return 'term--error'
  if (l.channel === 'warn') return 'term--warn'
  return ''
}

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    if (box.value) box.value.scrollTop = box.value.scrollHeight
  },
)
</script>

<style scoped>
.term { height: 300px; padding: 0; display: flex; flex-direction: column; overflow: hidden; }
.term-hd { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #151d33; color: #8b98bd; font-size: 11px; border-bottom: 1px solid #1d2742; flex: none; }
.dots { display: inline-flex; gap: 5px; }
.dots i { width: 9px; height: 9px; border-radius: 50%; }
.dots i:nth-child(1) { background: #f2757a; }
.dots i:nth-child(2) { background: #f0b429; }
.dots i:nth-child(3) { background: #3ecf8e; }
.term-body { flex: 1; overflow: auto; padding: 10px 12px; }
.term-hint { color: #5b6b96; }
</style>
