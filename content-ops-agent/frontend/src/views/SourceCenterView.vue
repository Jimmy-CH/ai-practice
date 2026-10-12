<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'

const route = useRoute()
const name = ref('产品说明')
const content = ref('')
const status = ref('')
async function importSource() {
  await api.post(`/projects/${route.params.id}/sources/text`, { name: name.value, content: content.value })
  status.value = '资料已导入'
}
async function generate() {
  await api.post(`/projects/${route.params.id}/generate`)
  status.value = '公告、FAQ 与海报草稿已生成'
}
</script>
<template><section><h2>来源中心</h2><input v-model="name" placeholder="资料名称"><textarea v-model="content" placeholder="粘贴产品文档、操作手册或发布说明"></textarea><button @click="importSource">导入资料</button><button @click="generate">一键生成</button><p>{{ status }}</p><RouterLink :to="`/projects/${route.params.id}/workspace`">进入创作审核工作台</RouterLink></section></template>
