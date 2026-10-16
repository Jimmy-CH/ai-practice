<template>
  <div class="app-shell">
    <TopBar />
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import TopBar from '@/components/TopBar.vue'
</script>

<style scoped>
.app-shell { min-height: 100%; display: flex; flex-direction: column; }
.app-main { flex: 1; width: 100%; max-width: 1560px; margin: 0 auto; padding: 16px 20px 32px; }
</style>
