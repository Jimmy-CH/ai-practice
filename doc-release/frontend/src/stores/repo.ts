import { defineStore } from 'pinia'
import * as api from '@/api/client'
import type { Preview, RefItem, Refs, Repo, RunDetail, Scenario } from '@/types'

// 仓库切换/预览加载的时序守卫：响应返回时序号新旧不符则丢弃，防慢响应覆盖新状态
let flowSeq = 0

export const useRepoStore = defineStore('repo', {
  state: () => ({
    repos: [] as Repo[],
    currentRepoId: null as number | null,
    refs: null as Refs | null,
    scenarios: [] as Scenario[],
    preview: null as Preview | null,
    loadingPreview: false,
    error: '',
    baseRef: '',
    headRef: '',
    versionLabel: '',
    tone: 'business' as 'business' | 'tech',
    mask: false,
  }),
  getters: {
    currentRepo(state): Repo | null {
      return state.repos.find((r) => r.id === state.currentRepoId) || null
    },
    isSample(state): boolean {
      return !!state.repos.find((r) => r.id === state.currentRepoId)?.is_sample
    },
    refOptions(state): RefItem[] {
      if (!state.refs) return []
      return [...state.refs.tags, ...state.refs.branches]
    },
  },
  actions: {
    async loadRepos() {
      this.repos = await api.getRepos()
      if (this.currentRepoId === null && this.repos.length) {
        await this.selectRepo(this.repos[0].id)
      }
    },
    async selectRepo(id: number) {
      const seq = ++flowSeq
      this.currentRepoId = id
      this.preview = null
      this.error = ''
      const refs = await api.getRefs(id)
      if (seq !== flowSeq) return
      this.refs = refs
      const scenarios = await api.getScenarios(id)
      if (seq !== flowSeq) return
      this.scenarios = scenarios
      const first = scenarios[0]
      if (first) {
        await this.applyScenario(first, seq)
      } else {
        const tags = refs.tags
        this.baseRef = tags[tags.length - 2]?.name || tags[tags.length - 1]?.name || refs.default_branch
        this.headRef = tags[tags.length - 1]?.name || refs.default_branch
        this.versionLabel = this.headRef
        await this.loadPreview(seq)
      }
    },
    async applyScenario(sc: Scenario, seq?: number) {
      this.baseRef = sc.base
      this.headRef = sc.head
      this.versionLabel = sc.version
      await this.loadPreview(seq)
    },
    async loadPreview(seq?: number) {
      const mySeq = seq ?? ++flowSeq
      if (this.currentRepoId === null || !this.baseRef || !this.headRef) return
      this.loadingPreview = true
      this.error = ''
      try {
        const preview = await api.getPreview(this.currentRepoId, this.baseRef, this.headRef)
        if (mySeq !== flowSeq) return   // 已被更新的切换/加载取代，丢弃过期响应
        this.preview = preview
      } catch (err) {
        if (mySeq !== flowSeq) return
        this.preview = null
        this.error = api.extractError(err)
      } finally {
        if (mySeq === flowSeq) this.loadingPreview = false
      }
    },
    async swapRefs() {
      const base = this.baseRef
      this.baseRef = this.headRef
      this.headRef = base
      await this.loadPreview()
    },
    async alignToRun(run: RunDetail) {
      // 用已完成运行的参数还原控制条（仓库/范围/口径/脱敏）与预览
      const seq = ++flowSeq
      this.tone = run.tone === 'tech' ? 'tech' : 'business'
      this.mask = run.mask
      if (run.repo_id === this.currentRepoId && this.refs) {
        this.baseRef = run.base_ref
        this.headRef = run.head_ref
        this.versionLabel = run.version_label
        await this.loadPreview(seq)
        return
      }
      this.currentRepoId = run.repo_id
      this.preview = null
      this.error = ''
      try {
        this.refs = await api.getRefs(run.repo_id)
      } catch {
        return
      }
      if (seq !== flowSeq) return
      try {
        this.scenarios = await api.getScenarios(run.repo_id)
      } catch {
        this.scenarios = []
      }
      if (seq !== flowSeq) return
      this.baseRef = run.base_ref
      this.headRef = run.head_ref
      this.versionLabel = run.version_label
      await this.loadPreview(seq)
    },
  },
})
