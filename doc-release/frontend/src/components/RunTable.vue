<template>
  <div class="scroll">
    <table class="table-simple">
      <thead>
        <tr>
          <th>时间</th>
          <th>仓库</th>
          <th>版本</th>
          <th>范围</th>
          <th>状态</th>
          <th>耗时</th>
          <th style="width: 150px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!runs.length">
          <td colspan="7" class="empty">暂无发布记录</td>
        </tr>
        <tr v-for="r in runs" :key="r.id">
          <td class="mono">{{ fmtTime(r.created_at) }}</td>
          <td>{{ r.repo_name }}</td>
          <td>{{ r.version_label }}</td>
          <td class="mono">{{ r.base_ref }}..{{ r.head_ref }}</td>
          <td><StatusBadge :status="r.status" /></td>
          <td>{{ duration(r) }}</td>
          <td>
            <el-button size="small" @click="$emit('view', r.id)">查看</el-button>
            <el-button size="small" type="danger" plain @click="$emit('remove', r.id)">删除</el-button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { RunSummary } from '@/types'
import StatusBadge from '@/components/StatusBadge.vue'

defineProps<{ runs: RunSummary[] }>()
defineEmits<{ view: [id: string]; remove: [id: string] }>()

function fmtTime(iso: string): string {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '-'
}

function duration(r: RunSummary): string {
  if (!r.finished_at) return '-'
  const ms = new Date(r.finished_at).getTime() - new Date(r.created_at).getTime()
  if (!Number.isFinite(ms) || ms <= 0) return '<1s'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
</script>
