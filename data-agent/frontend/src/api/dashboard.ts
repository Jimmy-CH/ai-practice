import { api } from './auth'

export interface DashboardData {
  summary: {
    total_revenue: number
    total_orders: number
    total_products: number
    monthly_revenue: number
  }
  daily_trend: {
    dates: string[]
    values: number[]
  }
  category_distribution: {
    labels: string[]
    values: number[]
  }
  top_products: {
    names: string[]
    values: number[]
  }
}

export async function getDashboard(): Promise<DashboardData> {
  const { data } = await api.get<DashboardData>('/agent/dashboard')
  return data
}
