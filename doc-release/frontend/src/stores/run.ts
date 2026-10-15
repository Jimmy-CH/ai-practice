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
        this.status = (ev.data as { status: string }).status
        const result = (ev.data as { result?: RunResult | null }).result
        if (result) this.result = result
        this.progress = 100
        this.closeStream()
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
