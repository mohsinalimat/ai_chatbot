<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <Sidebar
      :conversations="conversations"
      :current-conversation="currentConversation"
      @new-chat="handleNewChat"
      @select-conversation="handleSelectConversation"
      @delete-conversation="handleDeleteConversation"
    />

    <!-- Main Chat Area -->
    <div class="flex-1 flex flex-col">
      <!-- Header -->
      <ChatHeader
        :conversation="currentConversation"
        :ai-provider="selectedProvider"
        @change-provider="handleChangeProvider"
      />

      <!-- Messages Area -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto px-4 py-6 space-y-4"
      >
        <ChatMessage
          v-for="message in messages"
          :key="message.name || message._tempId"
          :message="message"
        />

        <!-- Streaming Message (live tokens) -->
        <div v-if="isStreaming && streamingContent" class="flex justify-start">
          <div class="max-w-3xl rounded-2xl px-6 py-4 shadow-sm bg-white border border-gray-200">
            <div class="text-gray-800">
              <div class="flex items-start gap-3">
                <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm font-semibold text-blue-600 flex-shrink-0">
                  AI
                </div>
                <div class="flex-1">
                  <!-- Tool calls in progress -->
                  <div v-if="streamToolCalls.length > 0" class="mb-3">
                    <div
                      v-for="(tc, idx) in streamToolCalls"
                      :key="idx"
                      class="flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded-lg mb-2"
                    >
                      <div
                        v-if="tc.status === 'executing'"
                        class="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin flex-shrink-0"
                      ></div>
                      <svg
                        v-else
                        class="w-4 h-4 text-green-600 flex-shrink-0"
                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                      </svg>
                      <span class="text-sm text-blue-800">
                        {{ formatToolName(tc.name) }}
                        <span v-if="tc.status === 'executing'" class="text-blue-500">...</span>
                      </span>
                    </div>
                  </div>

                  <!-- Streaming content -->
                  <div
                    v-if="streamingContent"
                    v-html="renderedStreamingContent"
                    class="markdown-body prose prose-sm max-w-none"
                  ></div>

                  <!-- Blinking cursor -->
                  <span class="inline-block w-2 h-5 bg-blue-600 animate-pulse ml-0.5 align-text-bottom"></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Typing indicator: shown while waiting for response (before streaming tokens arrive) -->
        <div v-if="isLoading && !streamingContent" class="flex justify-start">
          <div class="bg-white rounded-2xl px-6 py-4 shadow-sm border border-gray-200 max-w-3xl">
            <TypingIndicator />
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <ChatInput
        :disabled="isLoading || !currentConversation"
        :is-streaming="isStreaming"
        @send="handleSendMessage"
        @stop="handleStopGeneration"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import ChatHeader from '../components/ChatHeader.vue'
import ChatMessage from '../components/ChatMessage.vue'
import ChatInput from '../components/ChatInput.vue'
import TypingIndicator from '../components/TypingIndicator.vue'
import { chatAPI } from '../utils/api'
import { renderMarkdown } from '../utils/markdown'
import { useStreaming } from '../composables/useStreaming'
import { useSocket } from '../composables/useSocket'

const conversations = ref([])
const currentConversation = ref(null)
const messages = ref([])
const isLoading = ref(false)
const selectedProvider = ref('OpenAI')
const messagesContainer = ref(null)
const streamingEnabled = ref(true)

// Streaming composable
const {
  streamingContent,
  isStreaming,
  toolCalls: streamToolCalls,
  streamError,
  startListening,
  stopListening,
  reset: resetStreaming,
} = useStreaming()

// Socket connection
const { initSocket, isConnected } = useSocket()

// Render streaming markdown content
const renderedStreamingContent = computed(() => {
  if (!streamingContent.value) return ''
  try {
    return renderMarkdown(streamingContent.value)
  } catch {
    return streamingContent.value
  }
})

onMounted(async () => {
  // Load settings and conversations in parallel
  const [settingsResult] = await Promise.all([
    chatAPI.getSettings().catch(() => null),
    loadConversations(),
  ])

  if (settingsResult?.success) {
    streamingEnabled.value = settingsResult.settings.enable_streaming ?? true
  }

  // Initialize Socket.IO connection if streaming is enabled
  if (streamingEnabled.value) {
    initSocket()
  }

  // Auto-create first conversation if none exist
  if (conversations.value.length === 0) {
    await handleNewChat()
  }
})

onUnmounted(() => {
  stopListening()
})

const loadConversations = async () => {
  try {
    const response = await chatAPI.getConversations()
    if (response.success) {
      conversations.value = response.conversations
    }
  } catch (error) {
    console.error('Error loading conversations:', error)
  }
}

const handleNewChat = async () => {
  try {
    const response = await chatAPI.createConversation(
      'New Chat',
      selectedProvider.value
    )
    if (response.success) {
      await loadConversations()
      const newConv = conversations.value.find(c => c.name === response.conversation_id)
      if (newConv) {
        currentConversation.value = newConv
        messages.value = []
      } else {
        currentConversation.value = response.data || {
          name: response.conversation_id,
          title: 'New Chat',
          ai_provider: selectedProvider.value,
        }
        messages.value = []
      }
    }
  } catch (error) {
    console.error('Error creating conversation:', error)
  }
}

const handleSelectConversation = async (conversation) => {
  // Stop any active streaming
  stopListening()
  resetStreaming()

  currentConversation.value = conversation
  await loadMessages(conversation.name)
}

const loadMessages = async (conversationId) => {
  try {
    const response = await chatAPI.getConversationMessages(conversationId)
    if (response.success) {
      messages.value = response.messages
      await nextTick()
      scrollToBottom()
    }
  } catch (error) {
    console.error('Error loading messages:', error)
  }
}

const handleSendMessage = async (content) => {
  if (!currentConversation.value || !content.trim()) return

  // Add user message optimistically
  const userMessage = {
    _tempId: `temp_${Date.now()}`,
    role: 'user',
    content: content,
    timestamp: new Date().toISOString(),
  }
  messages.value.push(userMessage)
  await nextTick()
  scrollToBottom()

  isLoading.value = true

  const useStream = streamingEnabled.value && isConnected.value

  try {
    if (useStream) {
      // Streaming mode: start listening before sending
      startListening(currentConversation.value.name)

      // HTTP response returns immediately with stream_id.
      // Tokens arrive via Socket.IO realtime events.
      const response = await chatAPI.sendMessageStreaming(
        currentConversation.value.name,
        content
      )

      if (!response.success) {
        stopListening()
        console.error('Streaming request failed:', response.error)
        isLoading.value = false
        return
      }

      // isLoading stays true until streaming ends (handled by watcher below)
    } else {
      // Non-streaming fallback
      const response = await chatAPI.sendMessage(
        currentConversation.value.name,
        content
      )

      if (response.success) {
        messages.value.push({
          _tempId: `temp_resp_${Date.now()}`,
          role: 'assistant',
          content: response.message,
          timestamp: new Date().toISOString(),
          tokens_used: response.tokens_used,
        })
      }

      isLoading.value = false
      await loadMessages(currentConversation.value.name)
      await loadConversations()
    }
  } catch (error) {
    console.error('Error sending message:', error)
    isLoading.value = false
    stopListening()
  }
}

const handleStopGeneration = () => {
  stopListening()
  isLoading.value = false
}

const handleDeleteConversation = async (conversationId) => {
  try {
    const response = await chatAPI.deleteConversation(conversationId)
    if (response.success) {
      await loadConversations()
      if (currentConversation.value?.name === conversationId) {
        currentConversation.value = null
        messages.value = []
      }
    }
  } catch (error) {
    console.error('Error deleting conversation:', error)
  }
}

const handleChangeProvider = (provider) => {
  selectedProvider.value = provider
}

const scrollToBottom = (force = false) => {
  if (messagesContainer.value) {
    const el = messagesContainer.value
    if (force) {
      el.scrollTop = el.scrollHeight
      return
    }
    // Smart scroll: only auto-scroll if user is near the bottom
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150
    if (isNearBottom || isStreaming.value || isLoading.value) {
      el.scrollTop = el.scrollHeight
    }
  }
}

// Format tool name for display
const formatToolName = (name) => {
  if (!name) return 'Tool'
  return name
    .replace(/^(get_|search_|list_|create_|update_|delete_)/, '')
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// When streaming ends, reload messages to get the persisted version
watch(isStreaming, async (newVal, oldVal) => {
  if (oldVal && !newVal && currentConversation.value) {
    // Stream just ended
    isLoading.value = false
    await loadMessages(currentConversation.value.name)
    await loadConversations()
    resetStreaming()
    // Force scroll after reload — use setTimeout to wait for charts/images to render
    await nextTick()
    scrollToBottom(true)
    setTimeout(() => scrollToBottom(true), 300)
  }
})

// Auto-scroll during streaming
watch(streamingContent, () => {
  nextTick(() => scrollToBottom())
})

// Auto-scroll on new messages
watch(messages, () => {
  nextTick(() => scrollToBottom())
}, { deep: true })

// Handle stream errors
watch(streamError, (error) => {
  if (error) {
    console.error('Stream error:', error)
    isLoading.value = false
  }
})
</script>
