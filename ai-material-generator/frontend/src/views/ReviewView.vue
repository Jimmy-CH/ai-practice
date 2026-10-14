<template>
  <div class="page">
    <h2>审核工作台</h2>
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250">
        <template #default="{ row }">
          <el-button size="small" @click="preview(row)">查看</el-button>
          <el-button size="small" type="success" @click="approve(row.id)">通过</el-button>
          <el-button size="small" type="danger" @click="reject(row.id)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="drawerVisible" size="60%" :title="previewItem?.title || '物料内容'">
      <div v-if="previewItem" class="preview-meta">
        <span>类型：{{ previewItem.material_type }}</span>
        <span>受众：{{ previewItem.audience }}</span>
        <span>提交时间：{{ formatTime(previewItem.updated_at) }}</span>
      </div>
      <div class="markdown-body" v-html="renderMarkdown(previewItem?.content || '')" />
    </el-drawer>

    <el-dialog
      v-model="dialogVisible"
      :title="pendingAction?.action === 'reject' ? '驳回原因' : '审核意见（选填）'"
      width="480px"
    >
      <el-input
        v-model="comment"
        type="textarea"
        :rows="4"
        :placeholder="pendingAction?.action === 'reject' ? '请说明驳回原因（必填）' : '可填写备注（选填）'"
      />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :type="pendingAction?.action === 'reject' ? 'danger' : 'primary'" @click="confirmReview">
          {{ pendingAction?.action === 'reject' ? '确认驳回' : '确认通过' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listPending, reviewMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'
import { renderMarkdown, formatTime } from '@/utils/markdown'

const materials = ref<Material[]>([])
const dialogVisible = ref(false)
const comment = ref('')
const pendingAction = ref<{ id: number; action: 'approve' | 'reject' } | null>(null)
const drawerVisible = ref(false)
const previewItem = ref<Material | null>(null)

async function load() {
  const res = await listPending()
  materials.value = res.data
}
function preview(row: Material) {
  previewItem.value = row
  drawerVisible.value = true
}
function approve(id: number) {
  pendingAction.value = { id, action: 'approve' }
  comment.value = ''
  dialogVisible.value = true
}
function reject(id: number) {
  pendingAction.value = { id, action: 'reject' }
  comment.value = ''
  dialogVisible.value = true
}
async function confirmReview() {
  if (!pendingAction.value) return
  const text = comment.value.trim()
  if (pendingAction.value.action === 'reject' && !text) {
    ElMessage.warning('请填写驳回原因')
    return
  }
  try {
    await reviewMaterial(pendingAction.value.id, pendingAction.value.action, text)
    ElMessage.success(pendingAction.value.action === 'reject' ? '已驳回' : '已通过')
    dialogVisible.value = false
    comment.value = ''
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '审核失败')
  }
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
