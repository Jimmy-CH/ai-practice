<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const pending = ref<any[]>([])
const drawer = ref(false)
const selected = ref<any>(null)
const comment = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    pending.value = (await api.get('/assets/pending')).data
  } finally { loading.value = false }
}

async function review(assetId: string, decision: string) {
  await api.post(`/assets/${assetId}/reviews`, { decision, comment: comment.value })
  ElMessage.success(decision === 'approved' ? '已通过' : '已驳回')
  comment.value = ''
  await load()
}

function showCitations(asset: any) {
  selected.value = asset
  drawer.value = true
}

onMounted(load)
</script>

<template>
  <section>
    <h2>审核工作台</h2>
    <el-table v-loading="loading" :data="pending" border>
      <el-table-column prop="project_name" label="项目" />
      <el-table-column prop="kind" label="类型" />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" @click="showCitations(row)">查看引用</el-button>
          <el-button size="small" type="success" @click="review(row.id, 'approved')">通过</el-button>
          <el-button size="small" type="danger" @click="review(row.id, 'rejected')">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="drawer" title="证据引用" width="600px">
      <div v-for="(c, i) in selected?.citations" :key="i" style="margin-bottom:12px;border-left:3px solid #409eff;padding-left:8px">
        <p style="margin:0;color:#666;font-size:12px">来源：{{ c.source_id }}</p>
        <p>{{ c.text }}</p>
      </div>
      <el-input v-model="comment" placeholder="审核意见（驳回时必填）" type="textarea" :rows="3" />
    </el-dialog>
  </section>
</template>
