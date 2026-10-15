import { defineStore } from 'pinia'
import * as api from '@/api/client'
import type { Preview, RefItem, Refs, Repo, Scenario } from '@/types'

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
      this.currentRepoId = id
      this.preview = null
      this.error = ''
      this.refs = await api.getRefs(id)
      this.scenarios = await api.getScenarios(id)
      const first = this.scenarios[0]
      if (first) {
        await this.applyScenario(first)
      } else if (this.refs) {
        const tags = this.refs.tags
        this.baseRef = tags[tags.length - 2]?.name || tags[tags.length - 1]?.name || this.refs.default_branch
        this.headRef = tags[tags.length - 1]?.name || this.refs.default_branch
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
      if (this.currentRepoId === null || !this.baseRef || !this.headRef) return
      this.loadingPreview = true
      this.error = ''
      try {
        this.preview = await api.getPreview(this.currentRepoId, this.baseRef, this.headRef)
      } catch (err) {
        this.preview = null
        this.error = api.extractError(err)
      } finally {
        this.loadingPreview = false
      }
    },
    async swapRefs() {
      const base = this.baseRef
      this.baseRef = this.headRef
      this.headRef = base
      await this.loadPreview()
    },
  },
})
