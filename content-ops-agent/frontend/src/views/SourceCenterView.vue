<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
const route = useRoute(); const name = ref('产品说明'); const content = ref(''); const loading = ref(false); const generated = ref(false)
async function importSource() { loading.value=true; try { await api.post(`/projects/${route.params.id}/sources/text`, { name:name.value, content:content.value }); ElMessage.success('资料已导入') } catch { ElMessage.error('资料导入失败') } finally { loading.value=false } }
async function generate() { loading.value=true; try { await api.post(`/projects/${route.params.id}/generate`); generated.value=true; ElMessage.success('内容已生成') } catch (error:any) { ElMessage.error(error.response?.data?.detail ?? '生成失败') } finally { loading.value=false } }
</script>
<template><section><h2 class="page-title">来源中心</h2><el-steps :active="generated?2:1" finish-status="success" simple><el-step title="导入资料"/><el-step title="生成内容"/><el-step title="审核交付"/></el-steps><el-row :gutter="20" style="margin-top:20px"><el-col :span="16"><el-card header="产品与发布资料"><el-form label-position="top"><el-form-item label="资料名称"><el-input v-model="name"/></el-form-item><el-form-item label="资料内容"><el-input v-model="content" type="textarea" :rows="12" placeholder="粘贴产品文档、操作手册或发布说明"/></el-form-item><el-space><el-button :loading="loading" @click="importSource">导入资料</el-button><el-button type="primary" :loading="loading" @click="generate">一键生成内容</el-button></el-space></el-form></el-card></el-col><el-col :span="8"><el-card header="生成说明"><el-alert title="AI 仅根据已导入资料生成内容" type="info" :closable="false"/><el-divider/><el-button v-if="generated" type="success" plain @click="$router.push(`/projects/${route.params.id}/workspace`)">进入创作工作台</el-button></el-card></el-col></el-row></section></template>
