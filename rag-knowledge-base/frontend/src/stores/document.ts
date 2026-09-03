import { defineStore } from 'pinia'
import { ref } from 'vue'
import { documentApi } from '@/api/modules'
import { ElMessage } from 'element-plus'

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

export const useDocumentStore = defineStore('document', () => {
  const uploadStatus = ref<UploadStatus>('idle')
  const lastUploadedFilename = ref<string>('')

  async function uploadDocument(file: File): Promise<void> {
    // 前端校验
    const allowedExtensions = ['.pdf', '.txt']
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

    if (!allowedExtensions.includes(ext)) {
      ElMessage.warning('仅支持 PDF 和 TXT 格式')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      ElMessage.warning('文件大小不能超过 50MB')
      return
    }

    uploadStatus.value = 'uploading'
    try {
      const result = await documentApi.upload(file)
      uploadStatus.value = 'success'
      lastUploadedFilename.value = result.filename
      ElMessage.success(`${result.filename} ${result.message}`)
    } catch {
      uploadStatus.value = 'error'
      ElMessage.error('文档上传失败')
    }
  }

  function resetStatus(): void {
    uploadStatus.value = 'idle'
  }

  return { uploadStatus, lastUploadedFilename, uploadDocument, resetStatus }
})
