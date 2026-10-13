<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getDataSources, uploadDataSource, updateDataSource, deleteDataSource,
  type DataSourceOut,
} from '../api/datasource'

const sources = ref<DataSourceOut[]>([])
const loading = ref(false)
const uploading = ref(false)

// 编辑对话框
const editDialogVisible = ref(false)
const editingSource = ref<DataSourceOut | null>(null)
const editDescription = ref('')
const editColumnDescs = ref<{ column_name: string; description: string }[]>([])

async function loadSources() {
  loading.value = true
  try {
    sources.value = await getDataSources()
  } catch (e: any) {
    ElMessage.error('加载数据源失败: ' + (e.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function handleUpload(file: File) {
  uploading.value = true
  try {
    await uploadDataSource(file)
    ElMessage.success('上传成功')
    await loadSources()
  } catch (e: any) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    uploading.value = false
  }
}

function handleEdit(source: DataSourceOut) {
  editingSource.value = source
  editDescription.value = source.description
  editColumnDescs.value = source.columns.map(c => ({
    column_name: c.column_name,
    description: c.description,
  }))
  editDialogVisible.value = true
}

async function handleSaveEdit() {
  if (!editingSource.value) return
  try {
    await updateDataSource(editingSource.value.id, editDescription.value, editColumnDescs.value)
    ElMessage.success('更新成功')
    editDialogVisible.value = false
    await loadSources()
  } catch (e: any) {
    ElMessage.error('更新失败: ' + (e.message || '未知错误'))
  }
}

async function handleDelete(source: DataSourceOut) {
  try {
    await ElMessageBox.confirm(`确定删除数据源 "${source.original_filename}" 吗？删除后数据不可恢复。`, '确认删除', {
      type: 'warning',
    })
    await deleteDataSource(source.id)
    ElMessage.success('已删除')
    await loadSources()
  } catch {
    // 用户取消
  }
}

onMounted(loadSources)
</script>

<template>
  <div class="datasource-page">
    <div class="page-header">
      <h2>数据源管理</h2>
      <el-upload
        :show-file-list="false"
        :before-upload="(file: File) => { handleUpload(file); return false }"
        accept=".csv,.xlsx,.xls"
        :disabled="uploading"
      >
        <el-button type="primary" :loading="uploading">
          {{ uploading ? '上传中...' : '+ 上传数据文件' }}
        </el-button>
      </el-upload>
    </div>

    <p class="hint">支持 CSV、XLSX 格式。上传后 Agent 可以查询这些数据表。</p>

    <el-table :data="sources" v-loading="loading" border style="width: 100%; margin-top: 16px;">
      <el-table-column prop="table_name" label="表名" min-width="140" />
      <el-table-column prop="original_filename" label="原始文件" min-width="160" />
      <el-table-column prop="row_count" label="行数" width="80" align="center" />
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">
          {{ row.description || '—' }}
        </template>
      </el-table-column>
      <el-table-column label="列信息" min-width="250">
        <template #default="{ row }">
          <el-tag v-for="col in row.columns" :key="col.column_name" size="small" style="margin: 2px;">
            {{ col.column_name }} ({{ col.column_type }})
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑描述</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑描述对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑数据源描述" width="500px">
      <div v-if="editingSource">
        <el-form label-width="100px">
          <el-form-item label="表名">
            <span>{{ editingSource.table_name }}</span>
          </el-form-item>
          <el-form-item label="表描述">
            <el-input v-model="editDescription" type="textarea" :rows="2"
              placeholder="描述这张表的用途..." />
          </el-form-item>
          <el-divider>列描述</el-divider>
          <el-form-item v-for="(col, i) in editColumnDescs" :key="col.column_name"
            :label="`${col.column_name} (${editingSource.columns[i]?.column_type})`">
            <el-input v-model="col.description" placeholder="描述这个列的含义..." />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.datasource-page {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-header h2 {
  margin: 0;
  color: var(--text-primary);
}
.hint {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 8px 0 0;
}
</style>
