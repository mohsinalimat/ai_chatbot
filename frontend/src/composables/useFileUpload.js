/**
 * File Upload Composable
 *
 * Manages file selection, validation, preview generation, and pending state
 * for chat message attachments.
 */
import { ref, computed } from 'vue'

export const ALLOWED_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'application/pdf',
  'text/plain',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const MAX_FILES = 5

export function useFileUpload() {
  const pendingFiles = ref([]) // Array of { id, file, name, type, size, previewUrl, error }
  const isUploading = ref(false)
  const uploadError = ref(null)

  const hasFiles = computed(() => pendingFiles.value.length > 0)
  const hasImages = computed(() => pendingFiles.value.some((f) => IMAGE_TYPES.includes(f.type)))

  function addFiles(fileList) {
    // fileList can be from <input> or DataTransfer
    const files = Array.from(fileList)
    uploadError.value = null

    for (const file of files) {
      if (pendingFiles.value.length >= MAX_FILES) {
        uploadError.value = `Maximum ${MAX_FILES} files allowed`
        break
      }

      // Validate type
      if (!ALLOWED_TYPES.includes(file.type)) {
        uploadError.value = `"${file.name}" has unsupported type. Allowed: images, PDF, text, CSV, XLSX, DOCX`
        continue
      }

      // Validate size
      if (file.size > MAX_FILE_SIZE) {
        uploadError.value = `"${file.name}" exceeds 10MB limit`
        continue
      }

      const entry = {
        id: `file_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        file,
        name: file.name,
        type: file.type,
        size: file.size,
        previewUrl: null,
        error: null,
      }

      // Generate preview for images
      if (IMAGE_TYPES.includes(file.type)) {
        entry.previewUrl = URL.createObjectURL(file)
      }

      pendingFiles.value.push(entry)
    }
  }

  function removeFile(fileId) {
    const idx = pendingFiles.value.findIndex((f) => f.id === fileId)
    if (idx !== -1) {
      const entry = pendingFiles.value[idx]
      if (entry.previewUrl) {
        URL.revokeObjectURL(entry.previewUrl)
      }
      pendingFiles.value.splice(idx, 1)
    }
    uploadError.value = null
  }

  function clearFiles() {
    for (const entry of pendingFiles.value) {
      if (entry.previewUrl) {
        URL.revokeObjectURL(entry.previewUrl)
      }
    }
    pendingFiles.value = []
    uploadError.value = null
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return {
    pendingFiles,
    isUploading,
    uploadError,
    hasFiles,
    hasImages,
    addFiles,
    removeFile,
    clearFiles,
    formatFileSize,
  }
}
