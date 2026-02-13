<template>
  <div class="border-t border-gray-200 bg-white px-6 py-4">
    <div class="max-w-4xl mx-auto">
      <form @submit.prevent="handleSubmit" class="relative">
        <div class="flex items-end gap-3">
          <!-- Textarea -->
          <div class="flex-1 relative">
            <textarea
              ref="textareaRef"
              v-model="inputValue"
              @keydown="handleKeydown"
              :disabled="disabled && !isStreaming"
              placeholder="Type your message... (Shift+Enter for new line)"
              rows="1"
              class="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
              style="min-height: 52px; max-height: 200px;"
            ></textarea>

            <!-- Character count -->
            <div
              v-if="inputValue.length > 0"
              class="absolute bottom-2 right-3 text-xs text-gray-400"
            >
              {{ inputValue.length }}
            </div>
          </div>

          <!-- Stop Button (shown during streaming) -->
          <button
            v-if="isStreaming"
            type="button"
            @click="$emit('stop')"
            class="h-[52px] px-6 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-all duration-200 flex items-center gap-2 font-medium"
          >
            <Square :size="16" />
            Stop
          </button>

          <!-- Send Button (shown when not streaming) -->
          <button
            v-else
            type="submit"
            :disabled="disabled || !inputValue.trim()"
            class="h-[52px] px-6 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 font-medium"
          >
            <Send :size="18" />
            Send
          </button>
        </div>

        <!-- Hints -->
        <div class="mt-2 flex items-center justify-between text-xs text-gray-500">
          <div class="flex items-center gap-4">
            <span class="flex items-center gap-1">
              <Zap :size="14" />
              ERPNext tools enabled
            </span>
          </div>
          <span>
            Press Enter to send, Shift+Enter for new line
          </span>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { Send, Zap, Square } from 'lucide-vue-next'

const props = defineProps({
  disabled: Boolean,
  isStreaming: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['send', 'stop'])

const inputValue = ref('')
const textareaRef = ref(null)

const handleSubmit = () => {
  if (inputValue.value.trim() && !props.disabled) {
    emit('send', inputValue.value)
    inputValue.value = ''
    resetTextareaHeight()
  }
}

const handleKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}

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
    textarea.style.height = '52px'
  }
}

watch(inputValue, () => {
  nextTick(() => adjustTextareaHeight())
})
</script>
