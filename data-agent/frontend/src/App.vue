<script setup lang="ts">
import AgentChat from './components/AgentChat.vue'
</script>

<template>
  <div id="app">
    <header>
      <h1>📊 数据分析 Agent</h1>
    </header>
    <AgentChat />
  </div>
</template>

<style>
body {
  margin: 0;
  background: #ffffff;
}

header {
  text-align: center;
  padding: 16px;
  background: #1f2937;
  color: white;
}

header h1 {
  margin: 0;
  font-size: 20px;
}
</style>
