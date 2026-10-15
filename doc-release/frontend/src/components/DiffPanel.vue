<template>
  <section class="panel diff-panel">
    <div class="panel-header">
      <span>变更预览</span>
      <span v-if="store.preview" class="muted mono">{{ store.preview.base }} → {{ store.preview.head }}</span>
    </div>
    <div class="panel-body scroll diff-body">
      <div v-if="store.error" class="note-box note-box--error">{{ store.error }}</div>
      <div v-else-if="store.loadingPreview" class="empty">加载变更中…</div>
      <div v-else-if="!store.preview" class="empty">选择仓库与变更范围后预览变更</div>
      <template v-else>
        <div class="stat-row">
          <div class="stat"><b>{{ store.preview.stats.commits }}</b><span>提交</span></div>
          <div class="stat"><b>{{ store.preview.stats.files }}</b><span>文件</span></div>
          <div class="stat"><b>{{ store.preview.stats.modules }}</b><span>模块</span></div>
          <div class="stat"><b class="add-text">+{{ store.preview.stats.added }}</b><span>新增行</span></div>
          <div class="stat"><b class="del-text">-{{ store.preview.stats.removed }}</b><span>删除行</span></div>
          <div class="stat"><b>{{ store.preview.stats.days }}</b><span>跨度天</span></div>
        </div>

        <h4 class="section-title">提交记录</h4>
        <ul class="commit-list">
          <li v-for="c in store.preview.commits" :key="c.hash">
            <span class="mono muted">{{ c.hash }}</span>
            <span class="commit-subject">{{ c.subject }}</span>
            <span class="muted">{{ c.date }}</span>
          </li>
        </ul>

        <h4 class="section-title">文件 diff（{{ store.preview.files.length }}）</h4>
        <div v-for="f in store.preview.files" :key="f.path" class="diff-file">
          <div class="diff-file-head">
            <span class="tag" :class="statusClass(f.status)">{{ statusLabel(f.status) }}</span>
            <span class="diff-file-path">{{ f.path }}</span>
            <span class="muted">+{{ f.added }} / -{{ f.removed }}</span>
            <span v-if="f.truncated" class="chip chip--ghost">已截断</span>
          </div>
          <div v-if="f.binary" class="diff-lines"><div class="diff-line"><span class="diff-sign">·</span>二进制文件，未展示内容</div></div>
          <div v-else class="diff-lines">
            <div v-for="(l, i) in f.lines" :key="i" class="diff-line" :class="`diff-line--${l.t}`">
              <span class="diff-sign">{{ l.t === 'add' ? '+' : l.t === 'del' ? '-' : ' ' }}</span><span>{{ l.s }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRepoStore } from '@/stores/repo'

const store = useRepoStore()

function statusLabel(status: string): string {
  return { a: '新增', m: '修改', d: '删除' }[status] || '修改'
}

function statusClass(status: string): string {
  return { a: 'tag--add', d: 'tag--del' }[status] || 'tag--mod'
}
</script>

<style scoped>
.diff-panel { display: flex; flex-direction: column; min-height: 0; }
.diff-body { flex: 1; overflow: auto; max-height: calc(100vh - 260px); }
.section-title { margin: 14px 0 8px; font-size: 13px; color: var(--muted); }
.commit-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.commit-list li { display: flex; gap: 8px; font-size: 13px; }
.commit-subject { flex: 1; }
.add-text { color: var(--ok); }
.del-text { color: var(--danger); }
.note-box--error { background: #fdf3f3; border-color: #f5c6c8; color: #a03034; }
</style>
