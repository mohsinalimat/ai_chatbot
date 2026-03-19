<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar (always visible: collapsed=icon strip, expanded=full) -->
    <div class="flex-shrink-0 transition-all duration-300 ease-in-out overflow-hidden">
      <Sidebar
        :conversations="conversations"
        :current-conversation="currentConversation"
        :selected-provider="selectedProvider"
        :sidebar-collapsed="sidebarCollapsed"
        :search-results="searchResults"
        :is-searching="isSearching"
        :selected-language="selectedLanguage"
        :available-languages="availableLanguages"
        @new-chat="handleNewChat"
        @select-conversation="handleSelectConversation"
        @delete-conversation="handleDeleteConversation"
        @toggle-sidebar="toggleSidebar"
        @change-provider="handleChangeProvider"
        @change-language="handleChangeLanguage"
        @search="handleSearch"
      />
    </div>

    <!-- Main Chat Area -->
    <div class="flex-1 flex flex-col min-w-0">

      <!-- Empty state: centered greeting + input -->
      <div
        v-if="hasNoMessages"
        class="flex-1 flex flex-col items-center justify-center px-4"
      >
        <div class="text-center mb-8">
          <img
            v-if="userInfo.avatar"
            :src="userInfo.avatar"
            :alt="userInfo.fullname || 'User'"
            class="w-24 h-24 rounded-full object-cover mx-auto mb-4"
          />
          <div
            v-else
            class="w-24 h-24 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 flex items-center justify-center text-3xl font-semibold mx-auto mb-4"
          >
            {{ greetingInitials }}
          </div>
          <h1 class="text-2xl font-semibold text-gray-800 dark:text-gray-100 mb-2">
            Hello, {{ userInfo.fullname || 'there' }}!
          </h1>
          <p class="text-gray-500 dark:text-gray-400">How can I help you today?</p>
        </div>

        <div class="w-full max-w-2xl">
          <ChatInput
            :disabled="isLoading || !currentConversation"
            :is-streaming="isStreaming"
            @send="handleSendMessage"
            @stop="handleStopGeneration"
            @voice-start="warmupTTS"
          />
        </div>
      </div>

      <!-- Conversation state: messages + bottom-pinned input -->
      <template v-else>
        <!-- Conversation action bar -->
        <div class="flex items-center justify-end px-4 py-2 border-b border-gray-200 dark:border-gray-700">
          <button
            v-if="currentConversation && messages.length > 0"
            @click="handleExportConversation"
            :disabled="isExportingConversation"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title="Export entire conversation as PDF"
          >
            <Loader2 v-if="isExportingConversation" :size="14" class="animate-spin" />
            <FileDown v-else :size="14" />
            <span>{{ isExportingConversation ? 'Exporting...' : 'Export Chat PDF' }}</span>
          </button>
        </div>

        <!-- Messages Area -->
        <div
          ref="messagesContainer"
          class="flex-1 overflow-y-auto px-4 py-6 space-y-4"
        >
          <ChatMessage
            v-for="message in messages"
            :key="message.name || message._tempId"
            :message="message"
            :user-info="userInfo"
          />

          <!-- Streaming Message (live tokens) -->
          <div v-if="isStreaming && (streamingContent || agentPlan.length > 0)" class="flex justify-start">
            <div class="max-w-[85%] lg:max-w-5xl rounded-2xl px-6 py-4 shadow-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
              <div class="text-gray-800 dark:text-gray-200">
                <div class="flex items-start gap-3">
                  <img
                    :src="logoSvg"
                    alt="AI"
                    class="w-10 h-10 rounded-full flex-shrink-0"
                  />
                  <div class="flex-1">
                    <!-- Agent orchestration plan progress -->
                    <AgentThinking
                      :plan="agentPlan"
                      :auto-collapse="!!streamingContent"
                    />

                    <!-- Process step during streaming -->
                    <div v-if="processStep && agentPlan.length === 0" class="text-sm text-gray-500 dark:text-gray-400 mb-2 flex items-center gap-2">
                      <div class="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      {{ processStep }}
                    </div>

                    <!-- Tool calls in progress -->
                    <div v-if="streamToolCalls.length > 0" class="mb-3">
                      <div
                        v-for="(tc, idx) in streamToolCalls"
                        :key="idx"
                        class="flex items-center gap-2 p-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg mb-2"
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
                        <span class="text-sm text-blue-800 dark:text-blue-300">
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

          <!-- Typing indicator: shown while waiting for response (before streaming tokens or agent plan arrive) -->
          <div v-if="isLoading && !streamingContent && agentPlan.length === 0" class="flex justify-start">
            <div class="bg-white dark:bg-gray-800 rounded-2xl px-6 py-4 shadow-sm border border-gray-200 dark:border-gray-700 max-w-[85%] lg:max-w-5xl">
              <TypingIndicator :process-step="processStep" />
            </div>
          </div>

          <!-- Error message display -->
          <div v-if="displayError" class="flex justify-start">
            <div class="max-w-[85%] lg:max-w-5xl rounded-2xl px-6 py-4 shadow-sm bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
              <div class="flex items-start gap-3">
                <div class="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 dark:bg-red-800/40 flex items-center justify-center">
                  <svg class="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <div class="flex-1">
                  <p class="text-sm font-medium text-red-800 dark:text-red-300">{{ displayError }}</p>
                  <button
                    class="mt-2 text-xs text-red-600 dark:text-red-400 hover:underline"
                    @click="dismissError"
                  >Dismiss</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area (bottom-pinned) -->
        <ChatInput
          :disabled="isLoading || !currentConversation"
          :is-streaming="isStreaming"
          @send="handleSendMessage"
          @stop="handleStopGeneration"
          @voice-start="warmupTTS"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import ChatMessage from '../components/ChatMessage.vue'
import ChatInput from '../components/ChatInput.vue'
import TypingIndicator from '../components/TypingIndicator.vue'
import AgentThinking from '../components/AgentThinking.vue'
import { FileDown, Loader2 } from 'lucide-vue-next'
import { chatAPI } from '../utils/api'
import { renderMarkdown } from '../utils/markdown'
import { useStreaming } from '../composables/useStreaming'
import { useSocket } from '../composables/useSocket'
import logoSvg from '../assets/logo.svg'
import { useVoiceOutput } from '../composables/useVoiceOutput'

const conversations = ref([])
const currentConversation = ref(null)
const messages = ref([])
const isLoading = ref(false)
const selectedProvider = ref('OpenAI')
const messagesContainer = ref(null)
const streamingEnabled = ref(true)

// Language state
const selectedLanguage = ref('')
const availableLanguages = ref([])

// Current user info (fullname + avatar)
const userInfo = ref({ fullname: '', avatar: '' })

// Sidebar toggle (persisted in localStorage)
const sidebarCollapsed = ref(localStorage.getItem('ai_chatbot_sidebar') === 'collapsed')

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('ai_chatbot_sidebar', sidebarCollapsed.value ? 'collapsed' : 'expanded')
}

// PDF conversation export state
const isExportingConversation = ref(false)

// Error display state
const displayError = ref(null)

const dismissError = () => {
  displayError.value = null
}

// Search state
const searchResults = ref([])
const isSearching = ref(false)

const handleSearch = async (query) => {
  if (!query.trim()) {
    searchResults.value = []
    isSearching.value = false
    return
  }
  if (query.trim().length < 2) return
  isSearching.value = true
  try {
    const response = await chatAPI.searchConversations(query)
    if (response.success) {
      searchResults.value = response.conversations
    }
  } catch (error) {
    console.error('Search error:', error)
  } finally {
    isSearching.value = false
  }
}

// Voice output (TTS for auto-speak after voice input)
const { speak: speakResponse, isSupported: ttsSupported, warmup: warmupTTS } = useVoiceOutput()
const lastMessageWasVoice = ref(false)

// Empty state: no messages and not currently loading/streaming
const hasNoMessages = computed(() =>
  messages.value.length === 0 && !isLoading.value && !isStreaming.value
)

// User initials for greeting avatar fallback
const greetingInitials = computed(() => {
  const name = userInfo.value?.fullname || ''
  if (!name) return 'U'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  }
  return parts[0][0].toUpperCase()
})

// Streaming composable
const {
  streamingContent,
  isStreaming,
  toolCalls: streamToolCalls,
  processStep,
  streamError,
  agentPlan,
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
    if (settingsResult.settings.ai_provider) {
      selectedProvider.value = settingsResult.settings.ai_provider
    }
    if (settingsResult.user) {
      userInfo.value = settingsResult.user
    }
    if (settingsResult.settings.response_language !== undefined) {
      selectedLanguage.value = settingsResult.settings.response_language
    }
    if (settingsResult.settings.available_languages) {
      availableLanguages.value = settingsResult.settings.available_languages
    }
  }

  // Initialize Socket.IO connection if streaming is enabled
  if (streamingEnabled.value) {
    initSocket()
  }

  // Always start with a fresh new chat (enabled input + greeting)
  await handleNewChat()
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
  // Set up a pending (unsaved) conversation — no DB record yet.
  // The actual record is created lazily when the user sends the first message.
  currentConversation.value = {
    name: null,
    title: 'New Chat',
    ai_provider: selectedProvider.value,
    _pending: true,
  }
  messages.value = []
  selectedLanguage.value = ''
}

/**
 * Materialise a pending conversation into a real DB record.
 * Called once, right before the first message is sent.
 */
const ensureConversation = async () => {
  if (currentConversation.value && !currentConversation.value._pending) {
    return true // Already persisted
  }
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
      } else {
        currentConversation.value = response.data || {
          name: response.conversation_id,
          title: 'New Chat',
          ai_provider: selectedProvider.value,
        }
      }
      return true
    }
    return false
  } catch (error) {
    console.error('Error creating conversation:', error)
    return false
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
      // Load conversation-level language preference from session context
      if (response.session_context?.response_language) {
        selectedLanguage.value = response.session_context.response_language
      } else {
        selectedLanguage.value = ''
      }
      await nextTick()
      scrollToBottom()
    }
  } catch (error) {
    console.error('Error loading messages:', error)
  }
}

const handleSendMessage = async (payload) => {
  // Accept structured payload: { message, attachments, voiceInput }
  const message = typeof payload === 'string' ? payload : payload.message
  const attachments = typeof payload === 'string' ? [] : (payload.attachments || [])
  const voiceInput = typeof payload === 'string' ? false : (payload.voiceInput || false)

  if (!currentConversation.value || (!message.trim() && attachments.length === 0)) return

  // Lazy-create the conversation record on first message
  if (currentConversation.value._pending) {
    const created = await ensureConversation()
    if (!created) {
      displayError.value = 'Failed to create conversation. Please try again.'
      return
    }
  }

  // Clear any previous error
  displayError.value = null

  // Track whether this was a voice message (for auto-speak)
  lastMessageWasVoice.value = voiceInput

  // Upload files first (if any)
  let uploadedAttachments = null
  if (attachments.length > 0) {
    try {
      const uploadResults = await Promise.all(
        attachments.map((att) =>
          chatAPI.uploadFile(currentConversation.value.name, att.file)
        )
      )
      uploadedAttachments = uploadResults.filter((r) => r.success).map((r) => ({
        file_url: r.file_url,
        file_name: r.file_name,
        mime_type: r.mime_type,
        size: r.size,
        is_image: r.is_image,
      }))
    } catch (error) {
      console.error('File upload error:', error)
      // Continue sending message without attachments
    }
  }

  // Add user message optimistically
  const userMessage = {
    _tempId: `temp_${Date.now()}`,
    role: 'user',
    content: message,
    timestamp: new Date().toISOString(),
    attachments: uploadedAttachments,
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
        message,
        uploadedAttachments
      )

      if (!response.success) {
        stopListening()
        console.error('Streaming request failed:', response.error)
        displayError.value = response.error || 'Failed to send message. Please try again.'
        isLoading.value = false
        return
      }

      // isLoading stays true until streaming ends (handled by watcher below)
    } else {
      // Non-streaming fallback
      const response = await chatAPI.sendMessage(
        currentConversation.value.name,
        message,
        false,
        uploadedAttachments
      )

      if (response.success) {
        const assistantContent = response.message
        messages.value.push({
          _tempId: `temp_resp_${Date.now()}`,
          role: 'assistant',
          content: assistantContent,
          timestamp: new Date().toISOString(),
          tokens_used: response.tokens_used,
        })

        // Auto-speak if this was a voice-initiated message
        if (lastMessageWasVoice.value && ttsSupported.value && assistantContent) {
          setTimeout(() => speakResponse(assistantContent), 100)
          lastMessageWasVoice.value = false
        }
      } else {
        displayError.value = response.error || 'Failed to get a response. Please try again.'
      }

      isLoading.value = false
      await loadMessages(currentConversation.value.name)
      await loadConversations()
    }
  } catch (error) {
    console.error('Error sending message:', error)
    displayError.value = error?.message || 'An unexpected error occurred. Please try again.'
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

const handleChangeLanguage = async (language) => {
  selectedLanguage.value = language
  if (currentConversation.value && !currentConversation.value._pending) {
    try {
      await chatAPI.setConversationLanguage(currentConversation.value.name, language)
    } catch (error) {
      console.error('Error setting language:', error)
    }
  }
}

const handleExportConversation = async () => {
  if (!currentConversation.value || isExportingConversation.value) return
  isExportingConversation.value = true
  try {
    const result = await chatAPI.exportConversationPdf(currentConversation.value.name)
    if (result.success && result.file_url) {
      const a = document.createElement('a')
      a.href = result.file_url
      a.download = ''
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } else {
      displayError.value = result.error || 'Failed to export conversation as PDF.'
    }
  } catch (error) {
    console.error('Conversation PDF export error:', error)
    displayError.value = 'Failed to export conversation as PDF.'
  } finally {
    isExportingConversation.value = false
  }
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
    // Capture content before any resets — streamingContent may be cleared later
    const finalContent = streamingContent.value
    const wasVoice = lastMessageWasVoice.value

    isLoading.value = false
    await loadMessages(currentConversation.value.name)
    await loadConversations()
    resetStreaming()

    // Auto-speak after stream ends (voice input only).
    if (wasVoice && ttsSupported.value && finalContent) {
      setTimeout(() => {
        speakResponse(finalContent)
      }, 100)
      lastMessageWasVoice.value = false
    }

    // Force scroll after reload
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

// Handle stream errors — display in chat UI
watch(streamError, (error) => {
  if (error) {
    console.error('Stream error:', error)
    isLoading.value = false
    displayError.value = error
    nextTick(() => scrollToBottom(true))
  }
})
</script>
