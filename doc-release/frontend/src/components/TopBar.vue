<template>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand-block">
        <span class="brand-name">释文 DocRelease</span>
        <span class="brand-sub muted">发布文档自动生成</span>
      </div>
      <nav class="nav">
        <router-link class="nav-item" :class="{ 'nav-item--active': route.name === 'console' }" to="/">工作台</router-link>
        <router-link class="nav-item" :class="{ 'nav-item--active': String(route.name || '').startsWith('history') }" to="/history">发布历史</router-link>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.topbar { background: var(--panel); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 10; }
.topbar-inner { max-width: 1560px; margin: 0 auto; padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.brand-block { display: flex; align-items: baseline; gap: 10px; }
.brand-name { font-size: 18px; font-weight: 700; color: var(--brand); }
.brand-sub { font-size: 12px; }
.nav { display: flex; gap: 6px; }
.nav-item { padding: 6px 12px; border-radius: 8px; color: var(--muted); text-decoration: none; font-size: 13px; }
.nav-item--active { background: var(--brand-50); color: var(--brand); font-weight: 600; }
</style>
