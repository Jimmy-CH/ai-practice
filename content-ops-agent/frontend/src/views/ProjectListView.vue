<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createProject, listProjects, type Project } from '../api/projects'

const projects = ref<Project[]>([]); const dialog = ref(false); const loading = ref(false)
const form = ref({ name: '', theme: '', audience: '', tone: '专业' })
const pending = computed(() => projects.value.length)
async function load() { loading.value = true; try { projects.value = await listProjects() } catch { ElMessage.error('项目加载失败') } finally { loading.value = false } }
async function submit() { try { await createProject(form.value); dialog.value = false; form.value = { name: '', theme: '', audience: '', tone: '专业' }; ElMessage.success('项目创建成功'); await load() } catch { ElMessage.error('项目创建失败') } }
onMounted(load)
</script>
<template><section><div style="display:flex;justify-content:space-between;align-items:center"><div><h2 class="page-title">项目中心</h2><p>集中管理活动内容与发布工作流</p></div><el-button type="primary" @click="dialog=true">新建项目</el-button></div><el-row :gutter="16" style="margin:20px 0"><el-col :span="8"><el-card><el-statistic title="内容项目" :value="projects.length" /></el-card></el-col><el-col :span="8"><el-card><el-statistic title="待处理项目" :value="pending" /></el-card></el-col><el-col :span="8"><el-card><el-statistic title="已交付资产" :value="0" /></el-card></el-col></el-row><el-card><template #header><strong>项目列表</strong></template><el-table v-loading="loading" :data="projects" empty-text="暂无项目，点击右上角创建"><el-table-column prop="name" label="项目名称"/><el-table-column prop="theme" label="活动主题"/><el-table-column prop="audience" label="目标受众"/><el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" @click="$router.push(`/projects/${scope.row.id}/sources`)">进入项目</el-button></template></el-table-column></el-table></el-card><el-dialog v-model="dialog" title="新建内容项目" width="500"><el-form label-position="top"><el-form-item label="项目名称"><el-input v-model="form.name"/></el-form-item><el-form-item label="活动主题"><el-input v-model="form.theme"/></el-form-item><el-form-item label="目标受众"><el-input v-model="form.audience"/></el-form-item><el-form-item label="品牌语气"><el-input v-model="form.tone"/></el-form-item></el-form><template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="submit">创建</el-button></template></el-dialog></section></template>
