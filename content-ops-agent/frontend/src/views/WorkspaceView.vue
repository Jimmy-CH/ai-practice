<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'

type Asset = { id: string; kind: string; status: string; content: Record<string, unknown> }
const route = useRoute()
const assets = ref<Asset[]>([])
const message = ref('')
async function load() { assets.value = (await api.get(`/projects/${route.params.id}/assets`)).data }
async function approve(asset: Asset) { await api.post(`/assets/${asset.id}/reviews`, { decision: 'approved' }); await load() }
async function download(asset: Asset) { await api.get(`/assets/${asset.id}/download?format=html`); message.value = `${asset.kind} 已准备下载` }
async function publish(asset: Asset) { await api.post(`/assets/${asset.id}/deliveries`); message.value = `${asset.kind} 已模拟发布` }
onMounted(load)
</script>
<template><section><h2>创作与审核工作台</h2><p>{{ message }}</p><article v-for="asset in assets" :key="asset.id"><h3>{{ asset.kind }} · {{ asset.status }}</h3><pre>{{ asset.content }}</pre><button v-if="asset.status !== 'approved'" @click="approve(asset)">审核通过</button><button v-else @click="download(asset)">下载</button><button v-if="asset.status === 'approved'" @click="publish(asset)">模拟发布</button></article></section></template>
