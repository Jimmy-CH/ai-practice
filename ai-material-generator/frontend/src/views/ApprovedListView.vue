<template>
  <div class="page">
    <h2>已审核资产</h2>
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="download(row)">下载 Markdown</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listApproved, downloadMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'

const materials = ref<Material[]>([])
async function load() {
  const res = await listApproved()
  materials.value = res.data
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
</style>
