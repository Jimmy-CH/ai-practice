<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getShared, type SharedQueryDetail } from '../api/share'

use([CanvasRenderer, BarChart, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const route = useRoute()
const detail = ref<SharedQueryDetail | null>(null)
const error = ref('')
const loading = ref(true)

function buildEchartsOption(chartData: any) {
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#f1f5f9' : '#111827'
  if (chartData.type === 'pie') {
    return {
      backgroundColor: 'transparent',
      title: { text: chartData.title, textStyle: { color: textColor } },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: '60%',
        data: chartData.x_axis.map((label: string, i: number) => ({
          name: label, value: chartData.series[0].data[i],
        })),
      }],
    }
  }
  return {
    backgroundColor: 'transparent',
    title: { text: chartData.title, textStyle: { color: textColor } },
    tooltip: {},
    xAxis: { type: 'category', data: chartData.x_axis, axisLabel: { color: textColor } },
    yAxis: { type: 'value', axisLabel: { color: textColor } },
    series: chartData.series.map((s: any) => ({
      name: s.name, type: chartData.type, data: s.data,
    })),
  }
}

onMounted(async () => {
  const token = route.params.token as string
  try {
    detail.value = await getShared(token)
  } catch (e: any) {
    error.value = e.response?.status === 410 ? '该分享已过期' : '分享内容不存在'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="shared-view">
    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="error" class="error-state">
      <h2>{{ error }}</h2>
      <router-link to="/login">返回登录</router-link>
    </div>
    <div v-else-if="detail" class="content">
      <div class="header">
        <h2>📊 查询结果分享</h2>
        <p class="meta">
          分享时间: {{ new Date(detail.created_at).toLocaleString() }}
          <span v-if="detail.expires_at"> | 过期时间: {{ new Date(detail.expires_at).toLocaleString() }}</span>
        </p>
      </div>

      <div class="question-card">
        <strong>问题：</strong>{{ detail.question }}
      </div>

      <div class="answer-card">
        <strong>回答：</strong>
        <p>{{ detail.answer }}</p>
      </div>

      <div v-if="detail.chart_data" class="chart-card">
        <v-chart :option="buildEchartsOption(detail.chart_data)" style="height: 400px;" autoresize />
      </div>

      <div class="footer">
        <p>由 Data Analysis Agent 生成</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shared-view {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
  min-height: 100vh;
  background: var(--bg-secondary);
}
.loading-state, .error-state {
  text-align: center;
  padding: 60px 0;
  color: var(--text-secondary);
}
.error-state h2 { color: var(--text-primary); }
.header { margin-bottom: 24px; }
.header h2 { margin: 0 0 8px; color: var(--text-primary); }
.meta { color: var(--text-muted); font-size: 13px; margin: 0; }
.question-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border-left: 4px solid #3b82f6;
  color: var(--text-primary);
}
.answer-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  color: var(--text-primary);
  line-height: 1.6;
}
.chart-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.footer {
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
  margin-top: 40px;
}
</style>
