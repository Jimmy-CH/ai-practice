<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api/client'
type Asset = { id:string; kind:string; status:string; content:Record<string,unknown>; citations?:unknown[] }
const route=useRoute(); const assets=ref<Asset[]>([]); const loading=ref(false); const drawer=ref(false); const selected=ref<Asset|null>(null)
const grouped=computed(()=>['announcement','faq','poster'].map(kind=>({kind,items:assets.value.filter(item=>item.kind===kind)})))
async function load(){loading.value=true;try{assets.value=(await api.get(`/projects/${route.params.id}/assets`)).data}catch{ElMessage.error('资产加载失败')}finally{loading.value=false}}
async function approve(asset:Asset){await api.post(`/assets/${asset.id}/reviews`,{decision:'approved'});ElMessage.success('审核已通过');load()}
async function download(asset:Asset){await api.get(`/assets/${asset.id}/download?format=html`);ElMessage.success('下载任务已准备')}
async function publish(asset:Asset){await api.post(`/assets/${asset.id}/deliveries`);ElMessage.success('模拟发布完成')}
function citations(asset:Asset){selected.value=asset;drawer.value=true} onMounted(load)
</script>
<template><section><h2 class="page-title">创作审核工作台</h2><el-tabs v-loading="loading"><el-tab-pane v-for="group in grouped" :key="group.kind" :label="group.kind"><el-empty v-if="!group.items.length" description="暂无生成内容"/><el-row :gutter="16"><el-col v-for="asset in group.items" :key="asset.id" :span="12"><el-card><template #header><div style="display:flex;justify-content:space-between"><strong>{{asset.kind}}</strong><el-tag :type="asset.status==='approved'?'success':'warning'">{{asset.status}}</el-tag></div></template><pre style="white-space:pre-wrap">{{asset.content}}</pre><el-space><el-button v-if="asset.status!=='approved'" type="primary" @click="approve(asset)">审核通过</el-button><el-button @click="citations(asset)">查看引用</el-button><el-button v-if="asset.status==='approved'" @click="download(asset)">下载</el-button><el-popconfirm title="确认模拟发布？" @confirm="publish(asset)"><template #reference><el-button v-if="asset.status==='approved'" type="success">模拟发布</el-button></template></el-popconfirm></el-space></el-card></el-col></el-row></el-tab-pane></el-tabs><el-drawer v-model="drawer" title="证据引用"><pre>{{selected?.citations}}</pre></el-drawer></section></template>
