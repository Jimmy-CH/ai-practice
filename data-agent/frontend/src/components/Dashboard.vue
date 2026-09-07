<script setup lang="ts">
import { ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getDashboard, type DashboardData } from '../api/dashboard'

use([CanvasRenderer, BarChart, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const data = ref<DashboardData | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    data.value = await getDashboard()
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
})

function chartTextColor() {
  return document.documentElement.classList.contains('dark') ? '#f1f5f9' : '#111827'
}

function trendOption() {
  if (!data.value) return {}
  return {
    backgroundColor: 'transparent',
    title: { text: '近 30 天销售趋势', textStyle: { color: chartTextColor() } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.value.daily_trend.dates, axisLabel: { color: chartTextColor() } },
    yAxis: { type: 'value', axisLabel: { color: chartTextColor() } },
    series: [{ name: '销售额', type: 'line', data: data.value.daily_trend.values, smooth: true }],
  }
}

function categoryOption() {
  if (!data.value) return {}
  return {
    backgroundColor: 'transparent',
    title: { text: '品类销售占比', textStyle: { color: chartTextColor() } },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: '60%',
      data: data.value.category_distribution.labels.map((label, i) => ({
        name: label, value: data.value!.category_distribution.values[i],
      })),
    }],
  }
}

function topProductsOption() {
  if (!data.value) return {}
  return {
    backgroundColor: 'transparent',
    title: { text: 'TOP 10 热销商品', textStyle: { color: chartTextColor() } },
    tooltip: {},
    xAxis: { type: 'category', data: data.value.top_products.names, axisLabel: { rotate: 30, color: chartTextColor() } },
    yAxis: { type: 'value', axisLabel: { color: chartTextColor() } },
    series: [{ name: '销量', type: 'bar', data: data.value.top_products.values }],
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<template>
  <div v-loading="loading">
    <h2 style="margin: 0 0 20px 0; color: var(--text-primary);">数据仪表盘</h2>

    <template v-if="data">
      <!-- 统计卡片 -->
      <el-row :gutter="16" class="dash-row">
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">总销售额</div>
            <div class="stat-value">¥{{ formatNumber(data.summary.total_revenue) }}</div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">总订单数</div>
            <div class="stat-value">{{ data.summary.total_orders.toLocaleString() }}</div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">商品数量</div>
            <div class="stat-value">{{ data.summary.total_products }}</div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">近 30 天销售额</div>
            <div class="stat-value">¥{{ formatNumber(data.summary.monthly_revenue) }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表区域 -->
      <el-row :gutter="16" class="dash-row">
        <el-col :xs="24" :sm="16">
          <el-card shadow="hover" class="chart-card">
            <v-chart :option="trendOption()" style="height: 320px;" autoresize />
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="chart-card">
            <v-chart :option="categoryOption()" style="height: 320px;" autoresize />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="dash-row">
        <el-col :span="24">
          <el-card shadow="hover" class="chart-card">
            <v-chart :option="topProductsOption()" style="height: 350px;" autoresize />
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-empty v-else-if="!loading" description="数据加载失败" />
  </div>
</template>

<style scoped>
.dash-row {
  margin-bottom: 16px;
}
.stat-card {
  background: var(--bg-card);
  margin-bottom: 12px;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}
.chart-card {
  background: var(--bg-card);
  margin-bottom: 12px;
}
</style>
