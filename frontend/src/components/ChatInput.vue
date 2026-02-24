<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<template>
  <div class="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-6 py-4">
    <div class="max-w-4xl mx-auto">
      <form @submit.prevent="handleSubmit" class="relative">
        <!-- Attachment Preview Strip -->
        <div v-if="hasFiles" class="mb-2 flex flex-wrap gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div
            v-for="file in pendingFiles"
            :key="file.id"
            class="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 text-xs shadow-sm"
          >
            <img
              v-if="file.previewUrl"
              :src="file.previewUrl"
              :alt="file.name"
              class="w-8 h-8 rounded object-cover"
            />
            <FileText v-else :size="16" class="text-gray-500 dark:text-gray-400" />
            <span class="truncate max-w-[120px] dark:text-gray-200">{{ file.name }}</span>
            <span class="text-gray-400">{{ formatFileSize(file.size) }}</span>
            <button
              type="button"
              @click="removeFile(file.id)"
              class="ml-1 p-0.5 text-gray-400 hover:text-red-500 transition-colors"
            >
              <X :size="14" />
            </button>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- File Upload Button -->
          <button
            type="button"
            @click="triggerFileInput"
            :disabled="disabled && !isStreaming"
            class="h-10 w-10 flex-shrink-0 rounded-lg flex items-center justify-center bg-transparent hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Attach files (images, PDF, documents)"
          >
            <Paperclip :size="20" class="text-gray-500 dark:text-gray-400" />
          </button>
          <input
            ref="fileInputRef"
            type="file"
            multiple
            :accept="acceptTypes"
            class="hidden"
            @change="handleFileSelect"
          />

          <!-- Textarea with drag-and-drop -->
          <div
            class="flex-1 relative"
            @dragover.prevent="isDragOver = true"
            @dragleave="isDragOver = false"
            @drop.prevent="handleDrop"
          >
            <!-- Drag overlay -->
            <div
              v-if="isDragOver"
              class="absolute inset-0 bg-blue-50 dark:bg-blue-900/30 border-2 border-dashed border-blue-400 dark:border-blue-500 rounded-xl flex items-center justify-center text-blue-600 dark:text-blue-400 font-medium z-10"
            >
              Drop files here
            </div>

            <textarea
              ref="textareaRef"
              v-model="inputValue"
              @keydown="handleKeydown"
              @input="handleInput"
              :disabled="disabled && !isStreaming"
              placeholder="Type your message... (Shift+Enter for new line)"
              rows="1"
              class="w-full px-4 py-3 pr-12 border border-gray-300 dark:border-gray-600 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-500 disabled:bg-gray-100 dark:disabled:bg-gray-900 disabled:cursor-not-allowed transition-all"
              style="min-height: 44px; max-height: 200px;"
            ></textarea>

            <!-- Interim voice transcript -->
            <div
              v-if="isListening && interimTranscript"
              class="absolute bottom-2 left-4 text-sm text-gray-400 italic pointer-events-none"
            >
              {{ interimTranscript }}
            </div>

            <!-- Character count -->
            <div
              v-if="inputValue.length > 0"
              class="absolute bottom-2 right-3 text-xs text-gray-400"
            >
              {{ inputValue.length }}
            </div>

            <!-- @Mention Dropdown -->
            <div
              v-if="showMentionDropdown"
              ref="mentionDropdownRef"
              class="absolute bottom-full left-0 right-0 mb-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg max-h-64 overflow-y-auto z-20"
            >
              <div
                v-for="(option, idx) in filteredMentionOptions"
                :key="option.value || option.label"
                @click="selectMention(option)"
                @mouseenter="mentionSelectedIndex = idx"
                :class="[
                  'px-4 py-2.5 cursor-pointer flex items-center gap-3 text-sm transition-colors',
                  idx === mentionSelectedIndex ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' : 'hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200'
                ]"
              >
                <AtSign :size="14" class="text-gray-400 flex-shrink-0" />
                <div>
                  <div class="font-medium">{{ option.label }}</div>
                  <div v-if="option.description" class="text-xs text-gray-400">{{ option.description }}</div>
                </div>
              </div>
              <div v-if="filteredMentionOptions.length === 0" class="px-4 py-3 text-sm text-gray-400">
                No matches found
              </div>
            </div>
          </div>

          <!-- Microphone Button -->
          <button
            v-if="voiceSupported"
            type="button"
            @click="toggleVoice"
            :disabled="disabled && !isStreaming"
            :class="[
              'h-10 w-10 flex-shrink-0 rounded-lg flex items-center justify-center transition-all',
              isListening
                ? 'bg-red-500 hover:bg-red-600 animate-recording'
                : 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-700'
            ]"
            :title="isListening ? 'Stop recording' : 'Voice input'"
          >
            <Mic :size="20" :class="isListening ? 'text-white' : 'text-gray-500 dark:text-gray-400'" />
          </button>

          <!-- Stop Button (shown during streaming) -->
          <button
            v-if="isStreaming"
            type="button"
            @click="$emit('stop')"
            class="h-10 w-10 flex-shrink-0 rounded-lg flex items-center justify-center bg-red-500 text-white hover:bg-red-600 transition-all duration-200"
            title="Stop generating"
          >
            <Square :size="14" />
          </button>

          <!-- Send Button (shown when not streaming) -->
          <button
            v-else
            type="submit"
            :disabled="disabled || (!inputValue.trim() && !hasFiles)"
            class="h-10 w-10 flex-shrink-0 rounded-lg flex items-center justify-center bg-transparent hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 disabled:text-gray-300 dark:disabled:text-gray-600 disabled:cursor-not-allowed transition-all duration-200"
            title="Send message"
          >
            <Send :size="20" />
          </button>
        </div>

        <!-- Error Display -->
        <div v-if="uploadError || voiceError" class="mt-1 text-xs text-red-500">
          {{ uploadError || voiceError }}
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { Send, Square, Paperclip, Mic, X, FileText, AtSign } from 'lucide-vue-next'
import { useVoiceInput } from '../composables/useVoiceInput'
import { useFileUpload, ALLOWED_TYPES } from '../composables/useFileUpload'
import { chatAPI } from '../utils/api'

const props = defineProps({
  disabled: Boolean,
  isStreaming: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['send', 'stop', 'voice-start'])

const inputValue = ref('')
const textareaRef = ref(null)
const fileInputRef = ref(null)
const mentionDropdownRef = ref(null)
const isDragOver = ref(false)
const isVoiceMessage = ref(false)

// Voice input (auto-send after 2s silence)
const {
  isListening,
  transcript,
  interimTranscript,
  error: voiceError,
  isSupported: voiceSupported,
  silenceTimeout,
  startListening: startVoice,
  stopListening: stopVoice,
  resetTranscript,
} = useVoiceInput({ autoSendDelay: 2000 })

// File upload
const {
  pendingFiles,
  uploadError,
  hasFiles,
  addFiles,
  removeFile,
  clearFiles,
  formatFileSize,
} = useFileUpload()

const acceptTypes = computed(() => ALLOWED_TYPES.join(','))

// @Mention autocomplete state
const showMentionDropdown = ref(false)
const mentionQuery = ref('')
const mentionStartPos = ref(-1)
const mentionSelectedIndex = ref(0)
const mentionOptions = ref([])
const mentionSubOptions = ref([])
const mentionMode = ref('categories') // 'categories' or 'values'

// Base mention categories
const mentionCategories = [
  { label: 'Company', description: 'Select company', value: '@company', type: 'company' },
  { label: 'Period', description: 'Date range presets', value: '@period', type: 'period' },
  { label: 'Cost Center', description: 'Search cost centers', value: '@cost_center', type: 'cost_center' },
  { label: 'Department', description: 'Search departments', value: '@department', type: 'department' },
  { label: 'Warehouse', description: 'Search warehouses', value: '@warehouse', type: 'warehouse' },
  { label: 'Customer', description: 'Search customers', value: '@customer', type: 'customer' },
  { label: 'Item', description: 'Search items', value: '@item', type: 'item' },
  { label: 'Accounting Dimension', description: 'Accounting dimensions', value: '@accounting_dimension', type: 'accounting_dimension' },
]

const filteredMentionOptions = computed(() => {
  if (mentionMode.value === 'values') {
    return mentionSubOptions.value
  }
  const query = mentionQuery.value.toLowerCase()
  if (!query) return mentionCategories
  return mentionCategories.filter(
    (c) =>
      c.label.toLowerCase().includes(query) ||
      c.type.includes(query) ||
      (c.description && c.description.toLowerCase().includes(query))
  )
})

// When voice transcript updates, set input value
watch(transcript, (newVal) => {
  if (newVal) {
    inputValue.value = newVal
    isVoiceMessage.value = true
    nextTick(() => adjustTextareaHeight())
  }
})

// Auto-send when silence timeout fires (user stopped speaking)
watch(silenceTimeout, (timedOut) => {
  if (timedOut && inputValue.value.trim()) {
    stopVoice()
    nextTick(() => handleSubmit())
  }
})

const toggleVoice = () => {
  if (isListening.value) {
    stopVoice()
  } else {
    resetTranscript()
    isVoiceMessage.value = false
    emit('voice-start')
    startVoice()
  }
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileSelect = (event) => {
  addFiles(event.target.files)
  event.target.value = ''
}

const handleDrop = (event) => {
  isDragOver.value = false
  if (event.dataTransfer?.files) {
    addFiles(event.dataTransfer.files)
  }
}

const handleSubmit = () => {
  if ((!inputValue.value.trim() && !hasFiles.value) || props.disabled) return

  // Stop voice if still listening
  if (isListening.value) {
    stopVoice()
  }

  // Close mention dropdown
  closeMentionDropdown()

  // Build structured payload
  const payload = {
    message: inputValue.value,
    attachments: pendingFiles.value.map((f) => ({
      file: f.file,
      name: f.name,
      type: f.type,
      size: f.size,
      previewUrl: f.previewUrl,
    })),
    voiceInput: isVoiceMessage.value,
  }

  emit('send', payload)

  // Reset
  inputValue.value = ''
  clearFiles()
  isVoiceMessage.value = false
  resetTextareaHeight()
}

const handleKeydown = (event) => {
  // @Mention dropdown navigation
  if (showMentionDropdown.value) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      mentionSelectedIndex.value = Math.min(
        mentionSelectedIndex.value + 1,
        filteredMentionOptions.value.length - 1
      )
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      mentionSelectedIndex.value = Math.max(mentionSelectedIndex.value - 1, 0)
      return
    }
    if (event.key === 'Enter' && filteredMentionOptions.value.length > 0) {
      event.preventDefault()
      selectMention(filteredMentionOptions.value[mentionSelectedIndex.value])
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      closeMentionDropdown()
      return
    }
  }

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}

const handleInput = () => {
  // Detect @mention trigger
  const textarea = textareaRef.value
  if (!textarea) return

  const cursorPos = textarea.selectionStart
  const textBefore = inputValue.value.slice(0, cursorPos)

  // Find the last @ before cursor
  const lastAtIndex = textBefore.lastIndexOf('@')

  if (lastAtIndex !== -1) {
    // Check that @ is at start of input or preceded by whitespace
    const charBefore = lastAtIndex > 0 ? textBefore[lastAtIndex - 1] : ' '
    if (charBefore === ' ' || charBefore === '\n' || lastAtIndex === 0) {
      const query = textBefore.slice(lastAtIndex + 1)
      // Only show dropdown if query doesn't contain spaces (single token)
      if (!query.includes(' ')) {
        mentionQuery.value = query
        mentionStartPos.value = lastAtIndex
        mentionSelectedIndex.value = 0
        mentionMode.value = 'categories'
        showMentionDropdown.value = true
        return
      }
    }
  }

  closeMentionDropdown()
}

async function selectMention(option) {
  if (mentionMode.value === 'categories') {
    if (option.type === 'period') {
      try {
        const result = await chatAPI.getMentionValues('period')
        if (result.success && result.values) {
          mentionSubOptions.value = result.values.map((v) => ({
            label: v.label,
            description: v.value,
            insertValue: v.value,
          }))
          mentionMode.value = 'values'
          mentionSelectedIndex.value = 0
        }
      } catch {
        closeMentionDropdown()
      }
      return
    }

    if (option.type === 'accounting_dimension') {
      try {
        const result = await chatAPI.getMentionValues('accounting_dimension', '')
        if (result.success && result.values) {
          mentionSubOptions.value = result.values.map((dim) => ({
            label: dim.label,
            description: dim.description || '',
            _dimensionValues: dim.values || [],
            _isDimension: true,
            insertValue: null,
          }))
          mentionMode.value = 'values'
          mentionSelectedIndex.value = 0
        }
      } catch {
        closeMentionDropdown()
      }
      return
    }

    try {
      const result = await chatAPI.getMentionValues(option.type, '')
      if (result.success && result.values) {
        mentionSubOptions.value = result.values.map((v) => ({
          label: typeof v === 'string' ? v : v.label || v.name,
          description: typeof v === 'string' ? null : v.description || null,
          insertValue: typeof v === 'string' ? v : v.value || v.name || v.label,
        }))
        mentionMode.value = 'values'
        mentionSelectedIndex.value = 0
      }
    } catch {
      closeMentionDropdown()
    }
    return
  }

  // Values mode — check if this is a dimension type that needs drill-down
  if (option._isDimension && option._dimensionValues?.length > 0) {
    mentionSubOptions.value = option._dimensionValues.map((v) => ({
      label: typeof v === 'string' ? v : v.label || v.name,
      description: option.label,
      insertValue: typeof v === 'string' ? v : v.value || v.name || v.label,
    }))
    mentionSelectedIndex.value = 0
    return
  }

  // Insert the selected value
  if (option.insertValue) {
    insertMentionValue(option.insertValue)
  } else {
    insertMentionValue(option.label)
  }
}

function insertMentionValue(value) {
  const before = inputValue.value.slice(0, mentionStartPos.value)
  const after = inputValue.value.slice(textareaRef.value?.selectionStart || inputValue.value.length)
  inputValue.value = before + value + ' ' + after
  closeMentionDropdown()
  nextTick(() => {
    const newPos = before.length + value.length + 1
    textareaRef.value?.setSelectionRange(newPos, newPos)
    textareaRef.value?.focus()
    adjustTextareaHeight()
  })
}

function closeMentionDropdown() {
  showMentionDropdown.value = false
  mentionQuery.value = ''
  mentionStartPos.value = -1
  mentionSelectedIndex.value = 0
  mentionMode.value = 'categories'
  mentionSubOptions.value = []
}

// Close mention dropdown on click outside
function handleClickOutside(event) {
  if (
    mentionDropdownRef.value &&
    !mentionDropdownRef.value.contains(event.target) &&
    textareaRef.value !== event.target
  ) {
    closeMentionDropdown()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const adjustTextareaHeight = () => {
  const textarea = textareaRef.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
  }
}

const resetTextareaHeight = () => {
  const textarea = textareaRef.value
  if (textarea) {
    textarea.style.height = '44px'
  }
}

watch(inputValue, () => {
  nextTick(() => adjustTextareaHeight())
})
</script>
