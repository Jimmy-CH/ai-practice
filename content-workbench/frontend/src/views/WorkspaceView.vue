<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
import AssetEditor from './AssetEditor.vue'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id as string
const assets = ref<any[]>([])
const activeKind = ref('announcement')
const loading = ref(false)
const generating = ref(false)
const kinds = [
  { key: 'announcement', label: '公告' },
  { key: 'faq', label: 'FAQ' },
  { key: 'poster', label: '海报文案' },
]

async function load() {
  loading.value = true
  try {
    assets.value = (await api.get(`/projects/${projectId}/assets`)).data
  } finally { loading.value = false }
}

async function generate() {
  generating.value = true
  try {
    await api.post(`/projects/${projectId}/generate`)
    ElMessage.success('生成成功')
    await load()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '生成失败')
  } finally { generating.value = false }
}

function currentAsset(kind: string) {
  return assets.value.find((a) => a.kind === kind)
}

async function submit(kind: string) {
  const asset = currentAsset(kind)
  if (!asset) return
  await api.post(`/assets/${asset.id}/submit`)
  ElMessage.success('已提交审核')
  await load()
}

async function updateContent(kind: string, content: any) {
  const asset = currentAsset(kind)
  if (!asset) return
  await api.put(`/assets/${asset.id}`, { content })
  ElMessage.success('已保存')
  await load()
}

onMounted(load)
</script>

<template>
  <section>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>创作工作台</h2>
      <el-space>
        <el-button @click="router.push(`/projects/${projectId}/sources`)">资料中心</el-button>
        <el-button type="primary" :loading="generating" @click="generate">一键生成</el-button>
      </el-space>
    </div>
    <el-tabs v-model="activeKind" v-loading="loading">
      <el-tab-pane v-for="k in kinds" :key="k.key" :label="k.label" :name="k.key">
        <AssetEditor v-if="currentAsset(k.key)" :asset="currentAsset(k.key)" @save="(c) => updateContent(k.key, c)" @submit="submit(k.key)" />
        <el-empty v-else description="点击右上角一键生成" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
