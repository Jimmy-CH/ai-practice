<template>
  <section class="panel">
    <div class="panel-body control-grid">
      <div class="field">
        <label class="field-label">仓库</label>
        <el-select v-model="repoModel" placeholder="选择仓库" style="width: 220px">
          <el-option v-for="r in store.repos" :key="r.id"
                     :label="r.is_sample ? `${r.name}（内置示例）` : r.name" :value="r.id" />
        </el-select>
      </div>

      <div v-if="store.scenarios.length" class="field">
        <label class="field-label">内置场景</label>
        <div class="toolbar">
          <button v-for="sc in store.scenarios" :key="sc.id" class="chip-btn"
                  :class="{ 'chip-btn--active': sc.base === store.baseRef && sc.head === store.headRef }"
                  :title="sc.description" @click="store.applyScenario(sc)">
            {{ sc.name }} · {{ sc.version }}
          </button>
        </div>
      </div>

      <div class="field">
        <label class="field-label">变更范围</label>
        <div class="toolbar">
          <el-select v-model="baseModel" style="width: 148px" @change="store.loadPreview()">
            <el-option v-for="r in store.refOptions" :key="`b-${r.name}`" :label="r.name" :value="r.name" />
          </el-select>
          <button class="swap-btn" title="交换 base/head" @click="store.swapRefs()">⇄</button>
          <el-select v-model="headModel" style="width: 148px" @change="store.loadPreview()">
            <el-option v-for="r in store.refOptions" :key="`h-${r.name}`" :label="r.name" :value="r.name" />
          </el-select>
        </div>
      </div>

      <div class="field">
        <label class="field-label">版本号</label>
        <el-input v-model="versionModel" style="width: 140px" placeholder="如 v2.14.0" />
      </div>

      <div class="field">
        <label class="field-label">展示口径</label>
        <el-radio-group v-model="toneModel" size="small">
          <el-radio-button value="business">业务</el-radio-button>
          <el-radio-button value="tech">技术</el-radio-button>
        </el-radio-group>
      </div>

      <div class="field">
        <label class="field-label">脱敏</label>
        <el-switch v-model="maskModel" />
      </div>

      <div class="field field--actions">
        <el-button type="primary" :loading="runStore.isActive" :disabled="!canRun" @click="onRun">
          {{ runStore.isActive ? '运行中…' : '开始生成' }}
        </el-button>
        <el-button v-if="runStore.isActive" @click="runStore.cancel()">取消</el-button>
      </div>
    </div>

    <div v-if="runStore.status !== 'idle'" class="run-progress">
      <el-progress :percentage="runStore.progress" :stroke-width="6"
                   :status="progressStatus" :show-text="false" />
      <span class="muted run-progress-text">进度 {{ runStore.progress }}%</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { extractError } from '@/api/client'
import { useRepoStore } from '@/stores/repo'
import { useRunStore } from '@/stores/run'

const store = useRepoStore()
const runStore = useRunStore()

const repoModel = computed({
  get: () => store.currentRepoId ?? undefined,
  set: (v: number | undefined) => {
    if (typeof v === 'number') void store.selectRepo(v)
  },
})

const baseModel = computed({ get: () => store.baseRef, set: (v: string) => { store.baseRef = v } })
const headModel = computed({ get: () => store.headRef, set: (v: string) => { store.headRef = v } })
const versionModel = computed({ get: () => store.versionLabel, set: (v: string) => { store.versionLabel = v } })
const toneModel = computed({
  get: () => store.tone,
  set: (v: string | number | boolean | undefined) => { store.tone = v === 'tech' ? 'tech' : 'business' },
})
const maskModel = computed({
  get: () => store.mask,
  set: (v: string | number | boolean) => { store.mask = Boolean(v) },
})

const canRun = computed(
  () => store.currentRepoId !== null && !!store.baseRef && !!store.headRef && !runStore.isActive,
)

const progressStatus = computed(() => {
  if (runStore.status === 'failed' || runStore.status === 'cancelled') return 'exception' as const
  if (runStore.status === 'succeeded' || runStore.status === 'degraded') return 'success' as const
  return undefined
})

async function onRun() {
  if (store.currentRepoId === null) return
  try {
    await runStore.startRun(store.currentRepoId, {
      base_ref: store.baseRef,
      head_ref: store.headRef,
      version_label: store.versionLabel || store.headRef,
      tone: store.tone,
      mask: store.mask,
    })
  } catch (err) {
    ElMessage.error(extractError(err))
  }
}
</script>

<style scoped>
.control-grid { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px 18px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 12px; color: var(--muted); }
.field--actions { margin-left: auto; flex-direction: row; align-items: center; gap: 8px; }
.chip-btn { border: 1px solid var(--line); background: var(--panel); cursor: pointer; padding: 4px 12px; border-radius: 999px; font-size: 12px; color: var(--muted); }
.chip-btn:hover { border-color: var(--brand); color: var(--brand); }
.chip-btn--active { background: var(--brand-50); border-color: var(--brand); color: var(--brand); font-weight: 600; }
.swap-btn { border: 1px solid var(--line); background: var(--panel); border-radius: 8px; width: 30px; height: 30px; cursor: pointer; color: var(--muted); }
.swap-btn:hover { color: var(--brand); border-color: var(--brand); }
.run-progress { display: flex; align-items: center; gap: 10px; padding: 0 14px 14px; }
.run-progress :deep(.el-progress) { flex: 1; }
.run-progress-text { font-size: 12px; white-space: nowrap; }
</style>
