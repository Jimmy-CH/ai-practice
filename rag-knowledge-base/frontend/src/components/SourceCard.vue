<template>
  <div class="source-card">
    <div class="source-icon">📎</div>
    <div class="source-info">
      <div class="source-name">{{ source.source }}</div>
      <div class="source-page">第 {{ source.page }} 页</div>
    </div>
    <el-tooltip :content="source.snippet" placement="top">
      <div class="source-snippet">{{ truncate(source.snippet, 40) }}</div>
    </el-tooltip>
  </div>
</template>

<script setup lang="ts">
import type { SourceItem } from '@/types'

defineProps<{
  source: SourceItem
}>()

function truncate(text: string, maxLen: number): string {
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text
}
</script>

<style scoped>
.source-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  cursor: default;
  transition: border-color 0.2s;
}

.source-card:hover {
  border-color: #4a4ae8;
}

.source-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.source-info {
  flex-shrink: 0;
}

.source-name {
  font-size: 12px;
  font-weight: 500;
  color: #333;
}

.source-page {
  font-size: 10px;
  color: #999;
}

.source-snippet {
  font-size: 11px;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
</style>
