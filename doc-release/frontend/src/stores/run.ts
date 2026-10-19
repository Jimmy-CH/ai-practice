import { defineStore } from 'pinia'
import * as api from '@/api/client'
import { subscribeRun, type SseHandle } from '@/api/sse'
import type { LogLine, RunDetail, RunResult, SseEvent, StepState } from '@/types'

function logKey(line: LogLine): string {
  return `${line.ts}|${line.tag}|${line.message}`
}

export const useRunStore = defineStore('run', {
  state: () => ({
    current: null as RunDetail | null,
    steps: [] as StepState[],
    logs: [] as LogLine[],
    status: 'idle',
    progress: 0,
    error: '',
    result: null as RunResult | null,
    stats: {} as Record<string, number>,
    handle: null as SseHandle | null,
    seen: new Set<string>(),
  }),
  getters: {
    isActive(state): boolean {
      return state.status === 'pending' || state.status === 'running'
    },
  },
  actions: {
    closeStream() {
      this.handle?.close()
      this.handle = null
    },
    reset() {
      this.closeStream()
      this.current = null
      this.steps = []
      this.logs = []
      this.status = 'idle'
      this.progress = 0
      this.error = ''
      this.result = null
      this.stats = {}
      this.seen = new Set()
    },
    applySnapshot(detail: RunDetail) {
      this.current = detail
      this.steps = detail.steps || []
      this.logs = detail.logs || []
      this.status = detail.status
      this.error = detail.error || ''
      this.result = detail.result
      this.stats = (detail.stats || {}) as Record<string, number>
      this.seen = new Set(this.logs.map(logKey))
      // 断线重连时没有历史 progress 事件，用步骤完成度还原进度条，避免归零后长时间空转
      if (detail.status === 'succeeded' || detail.status === 'degraded') {
        this.progress = 100
      } else {
        const total = this.steps.length || 1
        const finished = this.steps.filter((s) => s.status === 'done').length
        this.progress = Math.round((finished / total) * 100)
      }
    },
    applyEvent(ev: SseEvent) {
      if (ev.event === 'snapshot') {
        this.applySnapshot(ev.data.run as RunDetail)
      } else if (ev.event === 'step') {
        const { index, status, duration_ms } = ev.data as { index: number; status: StepState['status']; duration_ms?: number }
        const step = this.steps[index]
        if (step) {
          step.status = status
          if (duration_ms !== undefined) step.duration_ms = duration_ms
        }
        if (this.current) this.current.current_step = index
      } else if (ev.event === 'log') {
        const line = ev.data as LogLine
        const key = logKey(line)
        if (!this.seen.has(key)) {
          this.seen.add(key)
          this.logs.push(line)
        }
      } else if (ev.event === 'progress') {
        this.progress = (ev.data as { percent: number }).percent ?? this.progress
      } else if (ev.event === 'error') {
        this.error = (ev.data as { message?: string }).message || '运行失败'
      } else if (ev.event === 'done') {
        const data = ev.data as { status: string; result?: RunResult | null }
        this.status = data.status
        if (data.result) this.result = data.result
        // 只有成功收尾才代表全流程走完；失败/取消保留当时的进度，避免进度条满格误导
        if (data.status === 'succeeded' || data.status === 'degraded') {
          this.progress = 100
        }
        this.closeStream()
        // done 事件不含 artifacts，拉取完整详情补齐产物列表，终态后产物面板立即可渲染
        void this.refreshDetail()
      }
    },
    async refreshDetail() {
      const id = this.current?.id
      if (!id) return
      try {
        const detail = await api.getRun(id)
        if (this.current?.id !== id) return   // 已切换运行，丢弃过期结果
        this.current = detail
        if (detail.result) this.result = detail.result
      } catch (err) {
        // 后台补齐详情失败不应产生未处理拒绝；提示后由用户重进详情页重试
        if (this.current?.id === id) this.error = this.error || api.extractError(err)
      }
    },
    connect(runId: string) {
      this.handle = subscribeRun(
        runId,
        (ev) => this.applyEvent(ev),
        (err) => {
          this.error = api.extractError(err)
        },
      )
    },
    async startRun(
      repoId: number,
      payload: { base_ref: string; head_ref: string; version_label: string; tone: string; mask: boolean },
    ) {
      this.reset()
      const detail = await api.createRun({ repo_id: repoId, ...payload })
      localStorage.setItem('docrelease:lastRun', detail.id)
      this.applySnapshot(detail)
      this.connect(detail.id)
    },
    async attach(runId: string) {
      this.reset()
      const detail = await api.getRun(runId)
      this.applySnapshot(detail)
      if (this.isActive) this.connect(runId)
    },
    async cancel() {
      if (!this.current) return
      await api.cancelRun(this.current.id)
    },
  },
})
