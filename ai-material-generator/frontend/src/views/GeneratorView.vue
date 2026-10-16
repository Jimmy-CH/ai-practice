<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AnalysisResult, Material } from '../api/client'
import { parseDocument, generateMaterial, generateAllMaterials, updateGeneratedMaterial } from '../api/client'
import { saveFromGeneration, submitMaterial, listMaterials, downloadMaterial } from '@/api/materials'
import { updateAnalysis, type AnalysisUpdatePayload } from '@/api/analysis'
import { renderMarkdown } from '@/utils/markdown'
import { copyToClipboard } from '@/utils/clipboard'
import { Upload, Search, DocumentCopy, Download, Document, DocumentChecked, Warning, CircleCheck, RefreshRight, Refresh, Edit } from '@element-plus/icons-vue'

const title = ref('网点管家 V3.2.0 版本迭代说明')
const content = ref(`【版本】网点管家 V3.2.0\n【发布日期】2026-10-20\n【适用范围】全国加盟网点\n\n一、新增功能\n1. 新增「异常件一键上报」功能\n网点扫描异常件后，可在首页直接发起上报，系统自动带出运单号、异常类型、上报时间，无需手工填写。\n\n二、优化与调整\n1. 运单批量导入：导入失败时返回具体失败原因与失败行号，便于网点自行排错。\n2. 消息中心：重要通知将后台自动推送，先在小部分网点试点，逐步放开至 30% 网点。\n3. 在线客服：由「我的」调整至「首页 - 帮助中心」。\n4. 旧版对账单：统一使用新版对账单。\n\n三、注意事项\n1. 本次版本需网点管家升级至 V3.2.0 以上版本方可使用新功能。\n2. 派费日结数据存在 24 小时延迟，以财务系统最终数据为准。\n3. 升级期间请勿强制关闭 App，避免数据同步异常。\n\n四、风险提示\n如出现派费数据缺失，请勿重复提交申诉，等待系统次日补数即可。遇到问题请勿重复操作，及时联系区域客服。`)
const file = ref<File | null>(null)
const analysis = ref<AnalysisResult | null>(null)
const currentMaterial = ref<Material | null>(null)
const allMaterials = ref<Material[]>([])
const loading = ref(false)
const analysisCollapsed = ref(false)
const audience = ref('网点管理员')
const activeMaterialType = ref('version_announcement')

const editingCategory = ref<string | null>(null)
const editingIndex = ref<number>(-1)
const editingText = ref('')

const isEditingMaterial = ref(false)
const editingMaterialContent = ref('')

const submitting = ref(false)
const submittedKey = ref('')

const refreshingStatus = ref(false)
const materialAssetId = ref<number | null>(null)
const materialAssetStatus = ref<string | null>(null)

const audiences = ['网点管理员', '业务员', '内部汇报']
const materialTypes = [
  { key: 'version_announcement', label: '版本宣发稿', num: '01' },
  { key: 'operation_guide', label: '网点操作指引', num: '02' },
  { key: 'faq', label: 'FAQ 问答库', num: '03' },
  { key: 'push_script', label: '行者推送话术', num: '04' },
  { key: 'poster_script', label: '海报脚本', num: '05' },
  { key: 'training_outline', label: '培训课件大纲', num: '06' },
]

const stats = computed(() => {
  const lines = content.value.split('\n').length
  const chars = content.value.length
  return `${chars} 字 · ${lines} 行`
})

const currentMaterialKey = computed(() =>
  currentMaterial.value ? `${currentMaterial.value.material_type}|${currentMaterial.value.content}` : '',
)
const isSubmitted = computed(
  () => !!currentMaterialKey.value && submittedKey.value === currentMaterialKey.value,
)

watch(currentMaterialKey, () => {
  materialAssetId.value = null
  materialAssetStatus.value = null
})

const statusLabels: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已驳回',
}
const materialStatusText = computed(() =>
  materialAssetStatus.value ? statusLabels[materialAssetStatus.value] || materialAssetStatus.value : '未查询',
)
const canDownload = computed(() => materialAssetStatus.value === 'approved' && !!materialAssetId.value)
const downloadHint = computed(() => {
  if (materialAssetStatus.value === 'approved') return '下载已审核通过的物料'
  if (materialAssetStatus.value === 'pending_review') return '待审核，审核通过后可下载'
  if (materialAssetStatus.value === 'rejected') return '已驳回，请修改后重新提交审核'
  if (materialAssetStatus.value === 'draft') return '资产为草稿，请先提交审核'
  return '请先点击「刷新审核状态」查询审核结果'
})

function onFileChange(raw: any) {
  const list = raw?.fileList || raw
  if (list && list.length > 0) {
    file.value = list[0].raw || list[0]
  }
}

function findMaterial(materialType: string): Material | undefined {
  return allMaterials.value.find(m => m.material_type === materialType)
}

async function doParse() {
  if (!title.value) {
    ElMessage.warning('请输入文档标题')
    return
  }
  if (!content.value && !file.value) {
    ElMessage.warning('请输入文档正文或上传 .docx 文件')
    return
  }
  loading.value = true
  try {
    analysis.value = await parseDocument(title.value, content.value, file.value || undefined, audience.value)
    if (analysis.value?.analysis_id) {
      ElMessage.success('解析完成（结果已保存）')
    } else {
      ElMessage.success('解析完成')
    }
    const result = await generateAllMaterials(title.value, analysis.value, audience.value)
    allMaterials.value = result.materials
    activeMaterialType.value = 'version_announcement'
    currentMaterial.value = findMaterial('version_announcement') || null
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '解析失败')
  } finally {
    loading.value = false
  }
}

async function doGenerate(materialType: string) {
  if (!analysis.value) return
  if (materialType === activeMaterialType.value && currentMaterial.value) {
    return
  }
  activeMaterialType.value = materialType
  const cached = findMaterial(materialType)
  if (cached) {
    currentMaterial.value = cached
    return
  }
  loading.value = true
  try {
    const material = await generateMaterial(title.value, analysis.value, audience.value, materialType)
    currentMaterial.value = material
    upsertLocalMaterial(material)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

function upsertLocalMaterial(material: Material) {
  const idx = allMaterials.value.findIndex(m => m.material_type === material.material_type)
  if (idx >= 0) {
    allMaterials.value[idx] = material
  } else {
    allMaterials.value.push(material)
  }
}

async function onAudienceChange() {
  if (!analysis.value) return
  allMaterials.value = []
  currentMaterial.value = null
  loading.value = true
  try {
    const result = await generateAllMaterials(title.value, analysis.value, audience.value)
    allMaterials.value = result.materials
    currentMaterial.value = findMaterial(activeMaterialType.value) || null
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

async function doGenerateAll() {
  if (!analysis.value) return
  if (allMaterials.value.length === materialTypes.length) {
    ElMessage.success('全部物料已生成')
    return
  }
  loading.value = true
  try {
    const result = await generateAllMaterials(title.value, analysis.value, audience.value)
    allMaterials.value = result.materials
    ElMessage.success('全部物料已生成')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

async function copyContent() {
  if (!currentMaterial.value) return
  // 内网 HTTP 部署下 navigator.clipboard 不可用，需降级到 execCommand（见 utils/clipboard.ts）
  const ok = await copyToClipboard(currentMaterial.value.content)
  if (ok) {
    ElMessage.success('已复制')
  } else {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

async function refreshReviewStatus() {
  const material = currentMaterial.value
  if (!material) return
  refreshingStatus.value = true
  try {
    const res = await listMaterials()
    const matched = (res.data as any[])
      .filter(
        (m) =>
          m.source_title === title.value &&
          m.material_type === material.meta.material_type &&
          m.audience === material.meta.audience,
      )
      .sort((a, b) => b.id - a.id)[0]
    if (matched) {
      materialAssetId.value = matched.id
      materialAssetStatus.value = matched.status
      ElMessage.success(`审核状态：${statusLabels[matched.status] || matched.status}`)
    } else {
      materialAssetId.value = null
      materialAssetStatus.value = null
      ElMessage.info('未找到该物料的审核记录，请先「保存并提交审核」')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '刷新失败')
  } finally {
    refreshingStatus.value = false
  }
}

function onDownloadClick() {
  if (!canDownload.value) {
    ElMessage.info(downloadHint.value)
    return
  }
  downloadCurrent()
}

async function downloadCurrent() {
  if (!materialAssetId.value) return
  try {
    const res = await downloadMaterial(materialAssetId.value)
    const blob = new Blob([res.data], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentMaterial.value?.title || 'material'}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '下载失败')
  }
}

async function saveAndSubmit() {
  if (!currentMaterial.value || !analysis.value) return
  try {
    await ElMessageBox.confirm('提交后将进入审核流程，审核期间不可编辑。确认提交？', '提交审核', { type: 'info' })
  } catch {
    return
  }
  submitting.value = true
  try {
    const created = (
      await saveFromGeneration({
        title: currentMaterial.value.title,
        content: currentMaterial.value.content,
        material_type: currentMaterial.value.meta.material_type,
        audience: currentMaterial.value.meta.audience,
        source_title: title.value,
        analysis: JSON.stringify(analysis.value),
      })
    ).data
    materialAssetId.value = created.id
    try {
      await submitMaterial(created.id)
      materialAssetStatus.value = 'pending_review'
      ElMessage.success('已提交审核，可在「我的资产」页面查看进度')
    } catch (e: any) {
      materialAssetStatus.value = 'draft'
      ElMessage.error(e.response?.data?.detail || '提交失败，物料已保存为草稿，可在「我的资产」页面重试')
    }
    submittedKey.value = currentMaterialKey.value
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

function editMaterial() {
  if (!currentMaterial.value) return
  isEditingMaterial.value = true
  editingMaterialContent.value = currentMaterial.value.content
}

function cancelMaterialEdit() {
  isEditingMaterial.value = false
  editingMaterialContent.value = ''
}

async function saveMaterialEdit() {
  if (!currentMaterial.value) return
  try {
    let materialId = currentMaterial.value.id
    if (!materialId && analysis.value) {
      // 兼容历史响应缺少缓存记录 id 的情况：重新获取一次以补齐（缓存命中时即时返回）
      const fresh = await generateMaterial(title.value, analysis.value, audience.value, activeMaterialType.value)
      materialId = fresh.id
      currentMaterial.value.id = fresh.id
    }
    if (!materialId) {
      ElMessage.warning('当前物料未生成或不存在缓存记录')
      return
    }
    const updated = await updateGeneratedMaterial(materialId, editingMaterialContent.value)
    currentMaterial.value.content = updated.content
    currentMaterial.value.cached = true
    upsertLocalMaterial(currentMaterial.value)
    isEditingMaterial.value = false
    ElMessage.success('物料内容已保存')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

function startEdit(category: string, index: number, text: string) {
  editingCategory.value = category
  editingIndex.value = index
  editingText.value = text
}

function cancelEdit() {
  editingCategory.value = null
  editingIndex.value = -1
  editingText.value = ''
}

function confirmEdit(category: string) {
  if (!analysis.value || editingIndex.value < 0) return
  const key = category as keyof AnalysisResult
  const list = analysis.value[key] as string[]
  list[editingIndex.value] = editingText.value
  cancelEdit()
}

function deleteItem(category: string, index: number) {
  if (!analysis.value) return
  const key = category as keyof AnalysisResult
  const list = analysis.value[key] as string[]
  list.splice(index, 1)
}

function addItem(category: string) {
  if (!analysis.value) return
  const key = category as keyof AnalysisResult
  const list = analysis.value[key] as string[]
  list.push('新条目')
  startEdit(category, list.length - 1, '新条目')
}

async function saveAnalysis() {
  if (!analysis.value || !analysis.value.analysis_id) {
    ElMessage.warning('请先解析文档')
    return
  }
  try {
    const payload: AnalysisUpdatePayload = {
      new_features: analysis.value['新增功能'],
      changes: analysis.value['变更与优化'],
      notices: analysis.value['注意事项'],
      risks: analysis.value['风险提示'],
    }
    analysis.value = await updateAnalysis(analysis.value.analysis_id, payload)
    ElMessage.success('解析结果已保存')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function regenerate() {
  if (!analysis.value) {
    ElMessage.warning('请先解析文档')
    return
  }
  loading.value = true
  try {
    const material = await generateMaterial(title.value, analysis.value, audience.value, activeMaterialType.value)
    currentMaterial.value = material
    upsertLocalMaterial(material)
    ElMessage.success('已重新生成')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重新生成失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon">+</div>
        <div>
          <h1 class="brand-title">AI 运营物料智能生成助手</h1>
          <p class="brand-subtitle">POC 概念验证：输入版本迭代文档，一键产出六类推广物料初稿</p>
        </div>
      </div>

      <div class="step-header">
        <div class="step-badge">1</div>
        <h2 class="step-title">输入文档</h2>
      </div>

      <el-input v-model="title" placeholder="请输入文档标题" class="input-title" />

      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".docx"
        class="uploader"
        @change="onFileChange"
      >
        <el-icon class="upload-icon"><Upload /></el-icon>
        <div class="upload-text">
          <span class="upload-link">点击或拖拽上传文档</span>
          <span>支持 .docx，也可直接粘贴正文</span>
        </div>
        <div v-if="file" class="upload-file">{{ file.name }}</div>
      </el-upload>

      <el-input
        v-model="content"
        type="textarea"
        :rows="16"
        placeholder="粘贴产品文档、版本迭代说明等文本"
        class="content-input"
      />

      <div class="stats">{{ stats }}</div>

      <el-button type="primary" :loading="loading" class="parse-btn" @click="doParse">
        <el-icon><Search /></el-icon>
        重新解析文档
      </el-button>
      <el-button :disabled="!analysis" class="save-analysis-btn" @click="saveAnalysis">
        <el-icon><DocumentChecked /></el-icon> 保存解析结果
      </el-button>
      <p class="parse-tip">解析结果可逐条勾选，未勾选的内容不会进入物料</p>
    </aside>

    <main class="main">
      <section v-show="!analysisCollapsed" class="section analysis-section">
        <div class="section-header">
          <div class="section-title">
            <span class="step-badge-inline">2</span>
            <span>AI 解析结果</span>
            <span v-if="analysis" class="section-status">解析完成</span>
          </div>
          <el-button text @click="analysisCollapsed = !analysisCollapsed">
            {{ analysisCollapsed ? '展开' : '收缩' }}
          </el-button>
        </div>

        <div v-if="analysis" class="analysis-grid">
          <el-card class="analysis-card" shadow="never">
            <div class="card-title">
              <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
              <span>功能点 · 新增</span>
              <span class="card-count">{{ analysis['新增功能'].length }}</span>
            </div>
            <ul class="card-list editable-list">
              <li v-for="(item, idx) in analysis['新增功能']" :key="'new-' + idx" class="edit-row">
                <template v-if="editingCategory === '新增功能' && editingIndex === idx">
                  <el-input v-model="editingText" size="small" @keyup.enter="confirmEdit('新增功能')" />
                  <el-button text size="small" @click="confirmEdit('新增功能')">确认</el-button>
                  <el-button text size="small" @click="cancelEdit">取消</el-button>
                </template>
                <template v-else>
                  <el-checkbox checked>{{ item }}</el-checkbox>
                  <span class="row-actions">
                    <el-button text size="small" @click="startEdit('新增功能', idx, item)">编辑</el-button>
                    <el-button text size="small" type="danger" @click="deleteItem('新增功能', idx)">删除</el-button>
                  </span>
                </template>
              </li>
            </ul>
            <el-button text size="small" class="add-btn" @click="addItem('新增功能')">+ 添加条目</el-button>
          </el-card>

          <el-card class="analysis-card" shadow="never">
            <div class="card-title">
              <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
              <span>变更与优化</span>
              <span class="card-count">{{ analysis['变更与优化'].length }}</span>
            </div>
            <ul class="card-list editable-list">
              <li v-for="(item, idx) in analysis['变更与优化']" :key="'opt-' + idx" class="edit-row">
                <template v-if="editingCategory === '变更与优化' && editingIndex === idx">
                  <el-input v-model="editingText" size="small" @keyup.enter="confirmEdit('变更与优化')" />
                  <el-button text size="small" @click="confirmEdit('变更与优化')">确认</el-button>
                  <el-button text size="small" @click="cancelEdit">取消</el-button>
                </template>
                <template v-else>
                  <el-checkbox checked>{{ item }}</el-checkbox>
                  <span class="row-actions">
                    <el-button text size="small" @click="startEdit('变更与优化', idx, item)">编辑</el-button>
                    <el-button text size="small" type="danger" @click="deleteItem('变更与优化', idx)">删除</el-button>
                  </span>
                </template>
              </li>
            </ul>
            <el-button text size="small" class="add-btn" @click="addItem('变更与优化')">+ 添加条目</el-button>
          </el-card>

          <el-card class="analysis-card" shadow="never">
            <div class="card-title">
              <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
              <span>注意事项</span>
              <span class="card-count">{{ analysis['注意事项'].length }}</span>
            </div>
            <ul class="card-list editable-list">
              <li v-for="(item, idx) in analysis['注意事项']" :key="'note-' + idx" class="edit-row">
                <template v-if="editingCategory === '注意事项' && editingIndex === idx">
                  <el-input v-model="editingText" size="small" @keyup.enter="confirmEdit('注意事项')" />
                  <el-button text size="small" @click="confirmEdit('注意事项')">确认</el-button>
                  <el-button text size="small" @click="cancelEdit">取消</el-button>
                </template>
                <template v-else>
                  <el-checkbox checked>{{ item }}</el-checkbox>
                  <span class="row-actions">
                    <el-button text size="small" @click="startEdit('注意事项', idx, item)">编辑</el-button>
                    <el-button text size="small" type="danger" @click="deleteItem('注意事项', idx)">删除</el-button>
                  </span>
                </template>
              </li>
            </ul>
            <el-button text size="small" class="add-btn" @click="addItem('注意事项')">+ 添加条目</el-button>
          </el-card>

          <el-card class="analysis-card warning" shadow="never">
            <div class="card-title">
              <el-icon color="#e6a23c"><Warning /></el-icon>
              <span>风险提示</span>
              <span class="card-count">{{ analysis['风险提示'].length }}</span>
            </div>
            <ul class="card-list editable-list">
              <li v-for="(item, idx) in analysis['风险提示']" :key="'risk-' + idx" class="edit-row">
                <template v-if="editingCategory === '风险提示' && editingIndex === idx">
                  <el-input v-model="editingText" size="small" @keyup.enter="confirmEdit('风险提示')" />
                  <el-button text size="small" @click="confirmEdit('风险提示')">确认</el-button>
                  <el-button text size="small" @click="cancelEdit">取消</el-button>
                </template>
                <template v-else>
                  <el-checkbox checked>{{ item }}</el-checkbox>
                  <span class="row-actions">
                    <el-button text size="small" @click="startEdit('风险提示', idx, item)">编辑</el-button>
                    <el-button text size="small" type="danger" @click="deleteItem('风险提示', idx)">删除</el-button>
                  </span>
                </template>
              </li>
            </ul>
            <el-button text size="small" class="add-btn" @click="addItem('风险提示')">+ 添加条目</el-button>
          </el-card>
        </div>
      </section>

      <section class="section generate-section">
        <div class="section-header">
          <div class="section-title">
            <span class="step-badge-inline">3</span>
            <span>物料生成</span>
          </div>
        </div>
        <p class="generate-subtitle">切换受众，文案语感自动改写</p>

        <div class="audience-tabs">
          <el-radio-group v-model="audience" size="large" @change="onAudienceChange">
            <el-radio-button v-for="a in audiences" :key="a" :label="a">{{ a }}</el-radio-button>
          </el-radio-group>
        </div>

        <div class="material-tabs">
          <el-check-tag
            v-for="mt in materialTypes"
            :key="mt.key"
            :checked="activeMaterialType === mt.key"
            class="material-tag"
            @change="doGenerate(mt.key)"
          >
            <span class="material-num">{{ mt.num }}</span>
            {{ mt.label }}
          </el-check-tag>
        </div>

        <p class="generate-hint">生成后可直接复制；当前物料审核状态：{{ materialStatusText }}</p>

        <div class="material-actions">
          <el-button :disabled="!currentMaterial || isEditingMaterial" @click="copyContent">
            <el-icon><DocumentCopy /></el-icon> 复制
          </el-button>
          <el-tooltip :content="downloadHint" placement="top">
            <span class="download-wrap" :class="{ 'is-blocked': !canDownload }" @click="onDownloadClick">
              <el-button :disabled="!canDownload">
                <el-icon><Download /></el-icon> 下载本页
              </el-button>
            </span>
          </el-tooltip>
          <el-button
            :disabled="!currentMaterial || isEditingMaterial"
            :loading="refreshingStatus"
            @click="refreshReviewStatus"
          >
            <el-icon><Refresh /></el-icon> 刷新审核状态
          </el-button>
          <el-button
            type="primary"
            :loading="submitting"
            :disabled="!currentMaterial || isEditingMaterial || isSubmitted"
            @click="saveAndSubmit"
          >
            <el-icon><DocumentChecked /></el-icon> {{ isSubmitted ? '已提交审核' : '保存并提交审核' }}
          </el-button>
          <el-button :disabled="!currentMaterial || isEditingMaterial" @click="editMaterial">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-button :disabled="!analysis" :loading="loading" @click="regenerate">
            <el-icon><RefreshRight /></el-icon> 重新生成
          </el-button>
          <el-button type="primary" :loading="loading" :disabled="!analysis" @click="doGenerateAll">
            <el-icon><Document /></el-icon> 导出全部
          </el-button>
        </div>

        <div v-if="currentMaterial" v-loading="loading" class="material-content">
          <h2 class="material-title">{{ currentMaterial.title }}</h2>
          <div class="material-meta">
            <span>受众：{{ currentMaterial.meta.audience }}</span>
            <span class="meta-sep">|</span>
            <span>物料类型：{{ currentMaterial.meta.material_type }}</span>
            <span class="meta-sep">|</span>
            <span>生成方式：{{ currentMaterial.meta.generator }}</span>
          </div>
          <template v-if="isEditingMaterial">
            <el-input
              v-model="editingMaterialContent"
              type="textarea"
              :rows="20"
              class="material-editor"
            />
            <div class="material-edit-actions">
              <el-button type="primary" @click="saveMaterialEdit">保存</el-button>
              <el-button @click="cancelMaterialEdit">取消</el-button>
            </div>
          </template>
          <div v-else class="markdown-body" v-html="renderMarkdown(currentMaterial.content)" />
        </div>

        <el-empty v-else description="点击「重新解析文档」生成物料" />
      </section>
    </main>
  </div>
</template>

<style scoped>
.page { display: flex; min-height: 100vh; background: #f8f9fc; }
.sidebar { width: 380px; flex-shrink: 0; background: #fff; padding: 24px; border-right: 1px solid #ebeef5; }
.brand { display: flex; gap: 12px; margin-bottom: 24px; }
.brand-icon { width: 40px; height: 40px; background: #7b2cbf; color: #fff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 24px; }
.brand-title { margin: 0; font-size: 18px; color: #303133; }
.brand-subtitle { margin: 4px 0 0; font-size: 12px; color: #909399; }
.step-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.step-badge { width: 28px; height: 28px; background: #7b2cbf; color: #fff; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; }
.step-title { margin: 0; font-size: 16px; }
.input-title { margin-bottom: 12px; }
.uploader { margin-bottom: 12px; }
.uploader :deep(.el-upload-dragger) { width: 100%; padding: 24px; }
.upload-icon { font-size: 32px; color: #7b2cbf; margin-bottom: 8px; }
.upload-text { display: flex; flex-direction: column; font-size: 13px; color: #606266; }
.upload-link { color: #7b2cbf; font-weight: 500; }
.upload-file { margin-top: 8px; color: #7b2cbf; font-size: 12px; }
.content-input { margin-bottom: 8px; }
.stats { text-align: right; font-size: 12px; color: #909399; margin-bottom: 12px; }
.parse-btn { width: 100%; margin-bottom: 8px; }
.parse-tip { font-size: 12px; color: #909399; text-align: center; margin: 0; }
.main { flex: 1; padding: 24px; overflow-y: auto; }
.section { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,.04); }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
.step-badge-inline { width: 24px; height: 24px; background: #7b2cbf; color: #fff; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.section-status { font-size: 12px; color: #67c23a; font-weight: normal; }
.analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.analysis-card :deep(.el-card__body) { padding: 16px; }
.card-title { display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 12px; }
.card-count { margin-left: auto; background: #f4e9ff; color: #7b2cbf; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.card-list { list-style: none; padding: 0; margin: 0; }
.card-list li { margin: 6px 0; font-size: 13px; }
.generate-subtitle { color: #909399; font-size: 13px; margin: -8px 0 16px; }
.audience-tabs { margin-bottom: 16px; }
.material-tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.material-tag { padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.material-tag.is-checked { background: #7b2cbf; color: #fff; }
.material-num { margin-right: 6px; opacity: .7; }
.generate-hint { color: #909399; font-size: 12px; margin: 0 0 12px; }
.material-actions { display: flex; gap: 10px; margin-bottom: 20px; }
.download-wrap { display: inline-block; }
.download-wrap.is-blocked :deep(.el-button) { pointer-events: none; }
.material-content { border: 1px solid #ebeef5; border-radius: 8px; padding: 24px; background: #fff; }
.material-title { margin: 0 0 12px; color: #7b2cbf; font-size: 22px; }
.material-meta { color: #606266; font-size: 13px; margin-bottom: 16px; padding: 12px; background: #fdf6ec; border-left: 4px solid #e6a23c; }
.meta-sep { margin: 0 8px; color: #c0c4cc; }
.markdown-body { line-height: 1.8; }
.markdown-body :deep(h3) { color: #303133; margin-top: 20px; }
.markdown-body :deep(ul) { padding-left: 20px; }
.markdown-body :deep(li) { margin: 6px 0; }
.editable-list .edit-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}
.editable-list .edit-row .el-input {
  flex: 1;
}
.editable-list .edit-row .el-checkbox {
  flex: 1;
  min-width: 0;
  height: auto;
  white-space: normal;
  align-items: flex-start;
  margin-right: 0;
}
.editable-list .edit-row .el-checkbox :deep(.el-checkbox__input) {
  margin-top: 3px;
}
.editable-list .edit-row .el-checkbox :deep(.el-checkbox__label) {
  line-height: 1.5;
  white-space: normal;
  word-break: break-word;
}
.row-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.add-btn {
  margin-top: 8px;
}
.save-analysis-btn {
  width: 100%;
  margin-top: 8px;
}
</style>
