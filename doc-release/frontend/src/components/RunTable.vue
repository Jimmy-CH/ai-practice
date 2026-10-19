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
          <td class="mono">{{ formatDateTime(r.created_at) }}</td>
          <td>{{ r.repo_name }}</td>
          <td>{{ r.version_label }}</td>
          <td class="mono">{{ r.base_ref }}..{{ r.head_ref }}</td>
          <td><StatusBadge :status="r.status" /></td>
          <td>{{ formatDuration(r.created_at, r.finished_at) }}</td>
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
import { formatDateTime, formatDuration } from '@/utils/datetime'

defineProps<{ runs: RunSummary[] }>()
defineEmits<{ view: [id: string]; remove: [id: string] }>()
</script>
