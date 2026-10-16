<template>
  <div class="page">
    <h2>已审核资产</h2>
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column prop="reviewer_username" label="审核人" width="100" />
      <el-table-column label="审核时间" width="170">
        <template #default="{ row }">{{ formatTime(row.reviewed_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button size="small" @click="preview(row)">查看</el-button>
          <el-button size="small" type="primary" @click="download(row)">下载 Markdown</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="drawerVisible" size="60%" :title="previewItem?.title || '物料内容'">
      <div v-if="previewItem" class="preview-meta">
        <span>类型：{{ previewItem.material_type }}</span>
        <span>受众：{{ previewItem.audience }}</span>
        <span>审核人：{{ previewItem.reviewer_username || '-' }}</span>
        <span>审核时间：{{ formatTime(previewItem.reviewed_at) }}</span>
      </div>
      <div class="markdown-body" v-html="renderMarkdown(previewItem?.content || '')" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listApproved, downloadMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'
import { renderMarkdown, formatTime } from '@/utils/markdown'

const materials = ref<Material[]>([])
const drawerVisible = ref(false)
const previewItem = ref<Material | null>(null)

async function load() {
  const res = await listApproved()
  materials.value = res.data
}
function preview(row: Material) {
  previewItem.value = row
  drawerVisible.value = true
}
async function download(row: Material) {
  const res = await downloadMaterial(row.id)
  const blob = new Blob([res.data], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${row.title}.md`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('开始下载')
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
.preview-meta { display: flex; gap: 16px; color: #909399; font-size: 13px; margin-bottom: 12px; }
.markdown-body { line-height: 1.8; }
.markdown-body :deep(h3) { color: #303133; margin-top: 20px; }
.markdown-body :deep(ul) { padding-left: 20px; }
</style>
