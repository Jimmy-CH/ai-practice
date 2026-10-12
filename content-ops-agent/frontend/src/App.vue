<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
const route = useRoute(); const router = useRouter()
const active = () => route.path.includes('/sources') ? 'sources' : route.path.includes('/workspace') ? 'workspace' : 'projects'
const go = (key: string) => { if (key === 'projects') router.push('/'); else if (route.params.id) router.push(`/projects/${route.params.id}/${key}`) }
</script>
<template><el-container class="app-shell"><el-aside width="240px" class="sidebar"><div class="brand">Content Ops Agent</div><el-menu :default-active="active()" background-color="#172033" text-color="#c0c4cc" active-text-color="#fff" @select="go"><el-menu-item index="projects">项目中心</el-menu-item><el-menu-item index="sources">来源中心</el-menu-item><el-menu-item index="workspace">创作工作台</el-menu-item></el-menu></el-aside><el-container><el-header class="topbar"><strong>企业内容运营后台</strong><el-tag type="success">在线</el-tag></el-header><el-main class="page"><RouterView /></el-main></el-container></el-container></template>
