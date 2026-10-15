export interface Repo {
  id: number
  name: string
  path: string
  is_sample: boolean
  created_at: string
}

export interface RefItem {
  name: string
  short: string
}

export interface Refs {
  branches: RefItem[]
  tags: RefItem[]
  default_branch: string
}

export interface Scenario {
  id: string
  name: string
  short: string
  version: string
  base: string
  head: string
  description: string
}

export interface Stats {
  commits: number
  files: number
  modules: number
  added: number
  removed: number
  days: number
}

export interface CommitInfo {
  hash: string
  author: string
  date: string
  subject: string
}

export interface DiffLine {
  t: 'add' | 'del' | 'ctx'
  s: string
}

export interface PreviewFile {
  status: 'a' | 'm' | 'd'
  path: string
  added: number
  removed: number
  binary: boolean
  truncated: boolean
  lines: DiffLine[]
}

export interface ModuleGroup {
  name: string
  files: string[]
}

export interface Preview {
  base: string
  head: string
  commits: CommitInfo[]
  files: PreviewFile[]
  stats: Stats
  modules: ModuleGroup[]
}

export type StepStatus = 'pending' | 'active' | 'done' | 'failed'

export interface StepState {
  index: number
  name: string
  status: StepStatus
  started_at?: string
  finished_at?: string
  duration_ms?: number
}

export interface LogLine {
  ts: string
  channel: string
  tag: string
  message: string
}

export interface Feature {
  tag: string
  risk: string
  breaking: boolean
  title: string
  biz: string
  tech: string
  visible: string
  scope: string
  acceptance: string
  action: string
  role: string
  paths: string[]
}

export interface LlmMeta {
  provider: string
  model: string
  prompt: string
  confidence: number
  inputChars: number
  outputChars: number
  glossaryHits: number
  lowConfidence: string[]
}

export interface RunMeta {
  runId: string
  repoName: string
  version: string
  branch: string
  headShort: string
  range: string
  trigger: string
  generatedAt: string
  stats: Stats
  modules: string[]
  pipeline: { name: string; ok: boolean; ms: number }[]
}

export interface ContractSignal {
  kind: string
  path: string
  message: string
}

export interface RunResult {
  features: Feature[]
  highlights: string[]
  lowConfidence: string[]
  llm: LlmMeta
  contractSignals: ContractSignal[]
  meta: RunMeta
}

export interface ArtifactInfo {
  kind: string
  filename: string
  bytes: number
}

export interface RunDetail {
  id: string
  repo_id: number
  repo_name: string
  base_ref: string
  head_ref: string
  version_label: string
  tone: string
  mask: boolean
  status: string
  current_step: number
  steps: StepState[]
  logs: LogLine[]
  stats: Stats | Record<string, never>
  result: RunResult | null
  error: string | null
  created_at: string
  finished_at: string | null
  artifacts: ArtifactInfo[]
}

export interface RunSummary {
  id: string
  repo_id: number
  repo_name: string
  base_ref: string
  head_ref: string
  version_label: string
  tone: string
  mask: boolean
  status: string
  current_step: number
  stats: Stats
  error: string | null
  created_at: string
  finished_at: string | null
}

export interface RunList {
  total: number
  items: RunSummary[]
}

export interface SseEvent {
  event: string
  data: any
}
