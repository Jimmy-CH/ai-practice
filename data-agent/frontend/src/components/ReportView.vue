<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getReports, createReport, toggleReport, deleteReport, runReport,
  type ReportOut,
} from '../api/report'

const reports = ref<ReportOut[]>([])
const loading = ref(false)
const runningId = ref<number | null>(null)

// 创建对话框
const createDialogVisible = ref(false)
const newName = ref('')
const newQuestion = ref('')
const newScheduleType = ref('daily')
const newScheduleTime = ref('09:00')

// 查看结果对话框
const resultDialogVisible = ref(false)
const resultContent = ref('')
const resultTitle = ref('')

async function loadReports() {
  loading.value = true
  try {
    reports.value = await getReports()
  } catch (e: any) {
    ElMessage.error('加载报告列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newName.value.trim() || !newQuestion.value.trim()) {
    ElMessage.warning('请填写名称和问题')
    return
  }
  try {
    await createReport(newName.value, newQuestion.value, newScheduleType.value, newScheduleTime.value)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    newName.value = ''
    newQuestion.value = ''
    await loadReports()
  } catch (e: any) {
    ElMessage.error('创建失败')
  }
}

async function handleToggle(report: ReportOut) {
  try {
    await toggleReport(report.id)
    await loadReports()
  } catch (e: any) {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(report: ReportOut) {
  try {
    await ElMessageBox.confirm(`确定删除报告 "${report.name}" 吗？`, '确认删除', { type: 'warning' })
    await deleteReport(report.id)
    ElMessage.success('已删除')
    await loadReports()
  } catch {
    // 取消
  }
}

async function handleRun(report: ReportOut) {
  runningId.value = report.id
  try {
    const result = await runReport(report.id)
    resultTitle.value = report.name
    resultContent.value = result.result
    resultDialogVisible.value = true
    await loadReports()
  } catch (e: any) {
    ElMessage.error('执行失败: ' + (e.message || '未知错误'))
  } finally {
    runningId.value = null
  }
}

function scheduleLabel(type: string): string {
  return type === 'daily' ? '每天' : '每周'
}

onMounted(loadReports)
</script>

<template>
  <div class="report-page">
    <div class="page-header">
      <h2>定时报告</h2>
      <el-button type="primary" @click="createDialogVisible = true">+ 新建报告</el-button>
    </div>

    <p class="hint">设置定时查询任务，点击"立即执行"可手动触发查看结果。</p>

    <el-table :data="reports" v-loading="loading" border style="width: 100%; margin-top: 16px;">
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="question" label="查询问题" min-width="250" show-overflow-tooltip />
      <el-table-column label="调度" width="120" align="center">
        <template #default="{ row }">{{ scheduleLabel(row.schedule_type) }} {{ row.schedule_time }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上次执行" width="160">
        <template #default="{ row }">
          {{ row.last_run_at ? new Date(row.last_run_at).toLocaleString() : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" align="center">
        <template #default="{ row }">
          <el-button size="small" @click="handleRun(row)" :loading="runningId === row.id">
            ▶ 执行
          </el-button>
          <el-button size="small" @click="handleToggle(row)">
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 查看结果 -->
    <el-dialog v-model="resultDialogVisible" :title="`报告结果: ${resultTitle}`" width="600px">
      <div class="report-result">{{ resultContent || '暂无结果' }}</div>
    </el-dialog>

    <!-- 创建对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建定时报告" width="500px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newName" placeholder="例如：每日销售汇总" />
        </el-form-item>
        <el-form-item label="查询问题">
          <el-input v-model="newQuestion" type="textarea" :rows="3"
            placeholder="例如：查询今天的销售总额和各品类占比" />
        </el-form-item>
        <el-form-item label="频率">
          <el-select v-model="newScheduleType" style="width: 120px;">
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行时间">
          <el-input v-model="newScheduleTime" placeholder="09:00" style="width: 120px;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.report-page {
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
.report-result {
  background: var(--bg-input);
  border-radius: 8px;
  padding: 16px;
  white-space: pre-wrap;
  line-height: 1.6;
  color: var(--text-primary);
  max-height: 400px;
  overflow-y: auto;
}
</style>
