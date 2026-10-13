<template>
  <div class="page">
    <h2>审核工作台</h2>
    <el-table :data="materials" style="margin-top: 20px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="material_type" label="类型" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="approve(row.id)">通过</el-button>
          <el-button size="small" type="danger" @click="reject(row.id)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" title="审核意见">
      <el-input v-model="comment" type="textarea" :rows="4" placeholder="选填" />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmReview">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listPending, reviewMaterial } from '@/api/materials'
import type { Material } from '@/api/materials'

const materials = ref<Material[]>([])
const dialogVisible = ref(false)
const comment = ref('')
const pendingAction = ref<{ id: number; action: 'approve' | 'reject' } | null>(null)

async function load() {
  const res = await listPending()
  materials.value = res.data
}
function approve(id: number) {
  pendingAction.value = { id, action: 'approve' }
  dialogVisible.value = true
}
function reject(id: number) {
  pendingAction.value = { id, action: 'reject' }
  dialogVisible.value = true
}
async function confirmReview() {
  if (!pendingAction.value) return
  await reviewMaterial(pendingAction.value.id, pendingAction.value.action, comment.value)
  ElMessage.success('审核完成')
  dialogVisible.value = false
  comment.value = ''
  load()
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
