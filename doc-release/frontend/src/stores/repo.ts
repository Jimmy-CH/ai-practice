import { defineStore } from 'pinia'
import * as api from '@/api/client'
import type { Preview, RefItem, Refs, Repo, RunDetail, Scenario } from '@/types'

// 时序守卫：repoSeq 守卫仓库初始化（refs/scenarios），previewSeq 守卫预览加载；
// 两者分离，避免预览操作作废进行中的仓库初始化。响应返回时序号不符则丢弃
let repoSeq = 0
let previewSeq = 0

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
      const seq = ++repoSeq
      this.currentRepoId = id
      this.preview = null
      this.error = ''
      const refs = await api.getRefs(id)
      if (seq !== repoSeq) return
      this.refs = refs
      const scenarios = await api.getScenarios(id)
      if (seq !== repoSeq) return
      this.scenarios = scenarios
      const first = scenarios[0]
      if (first) {
        await this.applyScenario(first)
      } else {
        const tags = refs.tags
        this.baseRef = tags[tags.length - 2]?.name || tags[tags.length - 1]?.name || refs.default_branch
        this.headRef = tags[tags.length - 1]?.name || refs.default_branch
        this.versionLabel = this.headRef
        await this.loadPreview()
      }
    },
    async applyScenario(sc: Scenario) {
      this.baseRef = sc.base
      this.headRef = sc.head
      this.versionLabel = sc.version
      await this.loadPreview()
    },
    async loadPreview() {
      const seq = ++previewSeq
      if (this.currentRepoId === null || !this.baseRef || !this.headRef) return
      this.loadingPreview = true
      this.error = ''
      try {
        const preview = await api.getPreview(this.currentRepoId, this.baseRef, this.headRef)
        if (seq !== previewSeq) return   // 已被更新的加载取代，丢弃过期响应
        this.preview = preview
      } catch (err) {
        if (seq !== previewSeq) return
        this.preview = null
        this.error = api.extractError(err)
      } finally {
        if (seq === previewSeq) this.loadingPreview = false
      }
    },
    async swapRefs() {
      const base = this.baseRef
      this.baseRef = this.headRef
      this.headRef = base
      await this.loadPreview()
    },
    async alignToRun(run: RunDetail) {
      // 用已完成运行的参数还原控制条（仓库/范围/口径/脱敏）与预览；响应先存局部，
      // 过序号守卫后才提交到共享状态，防被新切换取代的旧响应覆盖新仓库数据
      const seq = ++repoSeq
      this.tone = run.tone === 'tech' ? 'tech' : 'business'
      this.mask = run.mask
      if (run.repo_id === this.currentRepoId && this.refs) {
        this.baseRef = run.base_ref
        this.headRef = run.head_ref
        this.versionLabel = run.version_label
        await this.loadPreview()
        return
      }
      this.currentRepoId = run.repo_id
      this.preview = null
      this.error = ''
      let refs: Refs
      try {
        refs = await api.getRefs(run.repo_id)
      } catch {
        return
      }
      if (seq !== repoSeq) return
      this.refs = refs
      let scenarios: Scenario[] = []
      try {
        scenarios = await api.getScenarios(run.repo_id)
      } catch {
        scenarios = []
      }
      if (seq !== repoSeq) return
      this.scenarios = scenarios
      this.baseRef = run.base_ref
      this.headRef = run.head_ref
      this.versionLabel = run.version_label
      await this.loadPreview()
    },
  },
})
