<!-- src/App.vue -->
<template>
  <!-- 使用 <router-view /> 作为路由出口，匹配的组件会在这里渲染 -->
  <router-view />
</template>

<script setup lang="ts">
// 这里可以放置全局的逻辑，目前我们只需要一个路由出口
</script>

<style scoped>
/* 这里可以放置全局样式，或者重置一些默认样式 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: #f5f5f5;
}
</style>