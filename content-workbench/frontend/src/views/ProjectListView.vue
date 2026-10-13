<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const router = useRouter()
const projects = ref<any[]>([])
const dialog = ref(false)
const form = ref({ name: '', theme: '', audience: '', tone: '' })
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    projects.value = (await api.get('/projects')).data
  } finally { loading.value = false }
}

async function create() {
  await api.post('/projects', form.value)
  ElMessage.success('创建成功')
  dialog.value = false
  form.value = { name: '', theme: '', audience: '', tone: '' }
  await load()
}

async function remove(id: string) {
  await api.delete(`/projects/${id}`)
  ElMessage.success('删除成功')
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>项目列表</h2>
      <el-button type="primary" @click="dialog = true">新建项目</el-button>
    </div>
    <el-table v-loading="loading" :data="projects" border>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="theme" label="主题" />
      <el-table-column prop="audience" label="受众" />
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="router.push(`/projects/${row.id}/sources`)">资料</el-button>
          <el-button size="small" type="primary" @click="router.push(`/projects/${row.id}/workspace`)">工作台</el-button>
          <el-button size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialog" title="新建项目" width="500px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="主题"><el-input v-model="form.theme" type="textarea" /></el-form-item>
        <el-form-item label="受众"><el-input v-model="form.audience" /></el-form-item>
        <el-form-item label="语气"><el-input v-model="form.tone" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>
