<script setup lang="ts">
import { ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getAuditLogs, getUsageStats, type AuditLogOut, type UsageStats } from '../api/audit'

use([CanvasRenderer, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const logs = ref<AuditLogOut[]>([])
const stats = ref<UsageStats | null>(null)
const loading = ref(false)
const activeTab = ref('stats')
const actionFilter = ref('')

const trendOption = ref({})
const topUsersOption = ref({})

async function loadData() {
  loading.value = true
  try {
    const [logData, statsData] = await Promise.all([
      getAuditLogs(200, actionFilter.value || undefined),
      getUsageStats(),
    ])
    logs.value = logData
    stats.value = statsData

    // 构建趋势图
    trendOption.value = {
      backgroundColor: 'transparent',
      title: { text: '近 30 天查询趋势' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: statsData.daily_trend.map(d => d.date) },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: statsData.daily_trend.map(d => d.count), smooth: true, areaStyle: {} }],
    }

    // 构建 Top 用户图
    topUsersOption.value = {
      backgroundColor: 'transparent',
      title: { text: 'Top 活跃用户' },
      tooltip: {},
      xAxis: { type: 'category', data: statsData.top_users.map(u => u.username) },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: statsData.top_users.map(u => u.count) }],
    }
  } catch (e: any) {
    console.error('加载审计数据失败', e)
  } finally {
    loading.value = false
  }
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    query: '🔍 查询',
    upload: '📤 上传',
    delete: '🗑 删除',
    login: '🔑 登录',
    share: '🔗 分享',
  }
  return map[action] || action
}

onMounted(loadData)
</script>

<template>
  <div class="audit-page">
    <h2>操作审计与用量统计</h2>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="📊 用量统计" name="stats">
        <div v-if="stats" class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ stats.total_queries }}</div>
            <div class="stat-label">总查询数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.today_queries }}</div>
            <div class="stat-label">今日查询</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ stats.week_queries }}</div>
            <div class="stat-label">本周查询</div>
          </div>
        </div>

        <div class="charts-row">
          <v-chart :option="trendOption" style="height: 300px; flex: 2;" autoresize />
          <v-chart :option="topUsersOption" style="height: 300px; flex: 1;" autoresize />
        </div>

        <div v-if="stats && stats.top_questions.length" class="top-questions">
          <h3>🔥 热门查询</h3>
          <el-table :data="stats.top_questions" border size="small">
            <el-table-column prop="question" label="问题" min-width="300" />
            <el-table-column prop="user" label="用户" width="120" />
            <el-table-column prop="count" label="次数" width="80" align="center" />
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="📋 操作日志" name="logs">
        <div style="margin-bottom: 12px;">
          <el-select v-model="actionFilter" placeholder="筛选操作类型" clearable @change="loadData" style="width: 200px;">
            <el-option label="查询" value="query" />
            <el-option label="上传" value="upload" />
            <el-option label="删除" value="delete" />
            <el-option label="登录" value="login" />
          </el-select>
        </div>

        <el-table :data="logs" v-loading="loading" border size="small">
          <el-table-column prop="created_at" label="时间" width="180">
            <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column prop="username" label="用户" width="120" />
          <el-table-column prop="action" label="操作" width="100">
            <template #default="{ row }">{{ actionLabel(row.action) }}</template>
          </el-table-column>
          <el-table-column prop="detail" label="详情" min-width="300" show-overflow-tooltip />
          <el-table-column prop="ip_address" label="IP" width="140" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.audit-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.audit-page h2 {
  margin: 0 0 16px;
  color: var(--text-primary);
}
.stats-grid {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  flex: 1;
  background: var(--bg-card);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  border: 1px solid var(--border-color);
}
.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #3b82f6;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.charts-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.charts-row > * {
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}
.top-questions {
  margin-top: 16px;
}
.top-questions h3 {
  color: var(--text-primary);
  margin: 0 0 8px;
}
</style>
