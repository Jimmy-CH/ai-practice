<template>
  <div class="upload-area">
    <div class="upload-toggle" @click="expanded = !expanded">
      <span>📄 文档上传</span>
      <el-icon><ArrowUp v-if="expanded" /><ArrowDown v-else /></el-icon>
    </div>

    <div v-show="expanded" class="upload-panel">
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleFileChange"
        accept=".pdf,.txt"
      >
        <div class="upload-dragger">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">拖拽文件至此或 <em>点击上传</em></div>
          <div class="upload-hint">支持 PDF、TXT 格式，最大 50MB</div>
        </div>
      </el-upload>

      <div v-if="docStore.uploadStatus === 'uploading'" class="upload-progress">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在上传...</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled, ArrowDown, ArrowUp, Loading } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { useDocumentStore } from '@/stores/document'

const docStore = useDocumentStore()
const expanded = ref(false)

function handleFileChange(uploadFile: UploadFile): void {
  if (uploadFile.raw) {
    docStore.uploadDocument(uploadFile.raw)
  }
}
</script>

<style scoped>
.upload-area {
  font-size: 13px;
}

.upload-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  color: #666;
  border-radius: 6px;
  transition: background 0.2s;
}

.upload-toggle:hover {
  background: #f5f5f5;
}

.upload-panel {
  padding: 8px;
}

.upload-dragger {
  padding: 16px 0;
}

.upload-icon {
  font-size: 28px;
  color: #4a4ae8;
}

.upload-text {
  font-size: 12px;
  color: #666;
  margin-top: 6px;
}

.upload-text em {
  color: #4a4ae8;
  font-style: normal;
}

.upload-hint {
  font-size: 11px;
  color: #bbb;
  margin-top: 4px;
}

.upload-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0 0;
  font-size: 12px;
  color: #4a4ae8;
}
</style>
