<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createProject, listProjects, type Project } from '../api/projects'

const projects = ref<Project[]>([])
const form = ref({ name: '', theme: '', audience: '', tone: '专业' })
const error = ref('')
async function load() { projects.value = await listProjects() }
async function submit() {
  try { await createProject(form.value); form.value = { name: '', theme: '', audience: '', tone: '专业' }; await load() }
  catch { error.value = '项目创建失败，请检查后端服务。' }
}
onMounted(load)
</script>
<template><section><h2>内容项目</h2><form @submit.prevent="submit"><input v-model="form.name" required placeholder="项目名称"><input v-model="form.theme" required placeholder="活动主题"><input v-model="form.audience" required placeholder="目标受众"><input v-model="form.tone" required placeholder="品牌语气"><button>创建项目</button></form><p v-if="error">{{ error }}</p><ul><li v-for="project in projects" :key="project.id">{{ project.name }} · {{ project.theme }}</li></ul></section></template>
