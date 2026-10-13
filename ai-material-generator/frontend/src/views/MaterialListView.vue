<template>
  <div class="page">
    <el-page-header title="资产列表" @back="$router.back" />
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" width="120" />
      <el-table-column prop="audience" label="受众" width="120" />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button v-if="canEdit(row)" size="small" @click="$router.push(`/materials/${row.id}/edit`)">编辑</el-button>
          <el-button v-if="canSubmit(row)" size="small" type="primary" @click="submit(row.id)">提交审核</el-button>
          <el-button v-if="canDelete(row)" size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listMaterials, submitMaterial, deleteMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const materials = ref<Material[]>([])

function statusType(status: string) {
  const map: Record<string, string> = { draft: 'info', pending_review: 'warning', approved: 'success', rejected: 'danger' }
  return map[status] || 'info'
}
function statusLabel(status: string) {
  const map: Record<string, string> = { draft: '草稿', pending_review: '待审核', approved: '已通过', rejected: '已驳回' }
  return map[status] || status
}
function canEdit(row: Material) {
  return auth.isEditor && row.status !== 'pending_review'
}
function canSubmit(row: Material) {
  return auth.isEditor && (row.status === 'draft' || row.status === 'rejected')
}
function canDelete(row: Material) {
  return auth.isEditor && (row.status === 'draft' || row.status === 'rejected')
}

async function load() {
  const res = await listMaterials()
  materials.value = res.data
}
async function submit(id: number) {
  await submitMaterial(id)
  ElMessage.success('已提交审核')
  load()
}
async function remove(id: number) {
  await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
  await deleteMaterial(id)
  ElMessage.success('已删除')
  load()
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
