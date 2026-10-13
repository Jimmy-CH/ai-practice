<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id as string
const sources = ref<any[]>([])
const content = ref('')
const name = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const selectedSource = ref<any>(null)

async function load() {
  loading.value = true
  try {
    sources.value = (await api.get(`/projects/${projectId}/sources`)).data
  } finally { loading.value = false }
}

async function add() {
  if (!name.value || !content.value) return
  await api.post(`/projects/${projectId}/sources`, { name: name.value, content: content.value })
  ElMessage.success('已添加')
  name.value = ''
  content.value = ''
  await load()
}

async function remove(sourceId: string) {
  await api.delete(`/projects/${projectId}/sources/${sourceId}`)
  await load()
}

function view(source: any) {
  selectedSource.value = source
  dialogVisible.value = true
}

onMounted(load)
</script>

<template>
  <section>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>资料中心</h2>
      <el-space>
        <el-button @click="router.push('/projects')">返回列表</el-button>
        <el-button type="primary" @click="router.push(`/projects/${projectId}/workspace`)">进入工作台</el-button>
      </el-space>
    </div>
    <el-card title="粘贴资料" style="margin-bottom:16px">
      <el-input v-model="name" placeholder="资料名称" style="margin-bottom:8px" />
      <el-input v-model="content" type="textarea" :rows="6" placeholder="粘贴产品文档、操作手册等文本" />
      <el-button type="primary" style="margin-top:8px" @click="add">添加资料</el-button>
    </el-card>
    <el-table v-loading="loading" :data="sources" border>
      <el-table-column prop="name" label="资料名" />
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" @click="view(row)">查看</el-button>
          <el-button size="small" type="danger" @click="remove(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dialogVisible" title="资料内容" width="600px">
      <h3 v-if="selectedSource">{{ selectedSource.name }}</h3>
      <p style="white-space:pre-wrap;word-break:break-word">{{ selectedSource?.content }}</p>
    </el-dialog>
  </section>
</template>
