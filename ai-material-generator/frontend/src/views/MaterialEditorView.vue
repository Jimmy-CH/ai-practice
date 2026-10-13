<template>
  <div class="page">
    <el-page-header title="编辑资产" @back="$router.push('/materials')" />
    <el-form :model="form" label-position="top" style="margin-top: 20px">
      <el-form-item label="标题">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="类型">
        <el-input v-model="form.material_type" disabled />
      </el-form-item>
      <el-form-item label="受众">
        <el-input v-model="form.audience" disabled />
      </el-form-item>
      <el-form-item label="内容 (Markdown)">
        <el-input v-model="form.content" type="textarea" :rows="20" />
      </el-form-item>
      <el-button type="primary" @click="save">保存</el-button>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMaterial, updateMaterial } from '@/api/materials'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const form = reactive({ title: '', content: '', material_type: '', audience: '' })

async function load() {
  const res = await getMaterial(id)
  Object.assign(form, res.data)
}
async function save() {
  await updateMaterial(id, { title: form.title, content: form.content, material_type: form.material_type, audience: form.audience })
  ElMessage.success('保存成功')
  router.push('/materials')
}
onMounted(load)
</script>

<style scoped>
.page { padding: 20px; }
</style>
