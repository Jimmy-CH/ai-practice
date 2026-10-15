<template>
  <section class="panel">
    <div class="panel-header">
      <span>发布历史</span>
      <div class="toolbar">
        <span class="muted">共 {{ total }} 条</span>
        <el-button size="small" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <RunTable :runs="items" @view="onView" @remove="onRemove" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteRun, extractError, getRuns } from '@/api/client'
import RunTable from '@/components/RunTable.vue'
import type { RunSummary } from '@/types'

const router = useRouter()
const items = ref<RunSummary[]>([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getRuns(100, 0)
    items.value = data.items
    total.value = data.total
  } catch (err) {
    ElMessage.error(extractError(err))
  } finally {
    loading.value = false
  }
}

function onView(id: string) {
  void router.push(`/history/${id}`)
}

async function onRemove(id: string) {
  try {
    await ElMessageBox.confirm('删除后不可恢复，确认删除该次运行记录与归档产物？', '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteRun(id)
    ElMessage.success('已删除')
    await load()
  } catch (err) {
    ElMessage.error(extractError(err))
  }
}

onMounted(() => { void load() })
</script>
