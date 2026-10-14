<template>
  <div class="page">
    <el-page-header title="资产列表" @back="$router.back" />
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" width="110" />
      <el-table-column prop="audience" label="受众" width="110" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审核意见" min-width="200">
        <template #default="{ row }">
          <el-tooltip v-if="row.review_comment" :content="row.review_comment" placement="top">
            <span class="comment-text">{{ row.review_comment }}</span>
          </el-tooltip>
          <span v-else>-</span>
          <div v-if="row.reviewed_at" class="review-meta">
            {{ row.reviewer_username || '-' }} · {{ formatTime(row.reviewed_at) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button v-if="canEdit(row)" size="small" @click="edit(row)">编辑</el-button>
          <el-button v-if="canSubmit(row)" size="small" type="primary" @click="submit(row.id)">提交审核</el-button>
          <el-button v-if="canDelete(row)" size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listMaterials, submitMaterial, deleteMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/markdown'

const auth = useAuthStore()
const router = useRouter()
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
async function edit(row: Material) {
  if (row.status === 'approved') {
    try {
      await ElMessageBox.confirm('该资产已通过审核，保存修改后将回落为草稿并需重新审核。确认编辑？', '提示', { type: 'warning' })
    } catch {
      return
    }
  }
  router.push(`/materials/${row.id}/edit`)
}
async function submit(id: number) {
  try {
    await ElMessageBox.confirm('提交后将进入审核流程，审核期间不可编辑。确认提交？', '提交审核', { type: 'info' })
  } catch {
    return
  }
  try {
    await submitMaterial(id)
    ElMessage.success('已提交审核')
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  }
}
async function remove(id: number) {
  try {
    await ElMessageBox.confirm('确认删除？', '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteMaterial(id)
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
.comment-text {
  display: inline-block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.review-meta { color: #909399; font-size: 12px; margin-top: 2px; }
</style>
