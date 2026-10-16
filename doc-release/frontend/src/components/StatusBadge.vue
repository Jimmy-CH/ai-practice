<template>
  <span class="status" :class="`status--${status}`">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const LABELS: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  succeeded: '成功',
  degraded: '降级完成',
  failed: '失败',
  cancelled: '已取消',
  idle: '未运行',
}

const label = computed(() => LABELS[props.status] || props.status)
</script>
