<script setup lang="ts">
import { ref } from 'vue'
const status = ref('请在来源中心生成内容资产。')
</script>
<template><section><h2>创作与审核工作台</h2><p>在此编辑公告、FAQ 和海报，提交审核后下载或模拟发布。</p><p>{{ status }}</p></section></template>
