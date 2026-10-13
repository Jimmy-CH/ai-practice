<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const activeTab = ref(auth.isEditor ? 'approved' : 'deliveries')
const approved = ref<any[]>([])
const deliveries = ref<any[]>([])
const audit = ref<any[]>([])
const loading = ref(false)

async function loadApproved() {
  if (!auth.isEditor) return
  approved.value = (await api.get('/assets/approved')).data
}

async function loadDeliveries() {
  deliveries.value = (await api.get('/deliveries')).data
}

async function loadAudit() {
  if (!auth.isReviewer) return
  audit.value = (await api.get('/audit')).data
}

async function refresh() {
  loading.value = true
  try {
    await Promise.all([loadApproved(), loadDeliveries(), loadAudit()])
  } finally { loading.value = false }
}

async function download(asset: any, format: string) {
  const response = await api.get(`/assets/${asset.id}/download?format=${format}`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `${asset.kind}.${format === 'markdown' ? 'md' : 'html'}`
  a.click()
  window.URL.revokeObjectURL(url)
}

async function publish(asset: any) {
  await api.post(`/assets/${asset.id}/deliveries`)
  ElMessage.success('模拟发布完成')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <section v-loading="loading">
    <h2>{{ auth.isEditor ? '发布任务' : '发布与审计' }}</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane v-if="auth.isEditor" label="已审核资产" name="approved">
        <el-table :data="approved" border>
          <el-table-column prop="project_name" label="项目" />
          <el-table-column prop="kind" label="类型" />
          <el-table-column label="下载" width="180">
            <template #default="{ row }">
              <el-button size="small" @click="download(row, 'markdown')">Markdown</el-button>
              <el-button size="small" @click="download(row, 'html')">HTML</el-button>
            </template>
          </el-table-column>
          <el-table-column label="发布" width="120">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="publish(row)">模拟发布</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="发布任务" name="deliveries">
        <el-table :data="deliveries" border>
          <el-table-column prop="id" label="任务 ID" />
          <el-table-column prop="asset_id" label="资产 ID" />
          <el-table-column prop="channel" label="渠道" />
          <el-table-column prop="status" label="状态" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane v-if="auth.isReviewer" label="审计日志" name="audit">
        <el-table :data="audit" border>
          <el-table-column prop="created_at" label="时间" />
          <el-table-column prop="actor" label="操作者" />
          <el-table-column prop="action" label="动作" />
          <el-table-column prop="object_type" label="对象类型" />
          <el-table-column prop="object_id" label="对象 ID" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
