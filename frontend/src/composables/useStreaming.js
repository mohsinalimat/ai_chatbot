// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt
/**
 * Streaming Composable
 *
 * Manages real-time AI response streaming via Frappe's Socket.IO realtime events.
 * Listens for token chunks, tool calls, and stream lifecycle events.
 *
 * Phase 13A enhancements:
 * - Token buffering with 50ms debounce to reduce visual jitter
 * - requestAnimationFrame-based DOM updates for smooth rendering
 * - Streaming error recovery with retry support
 * - Stream activity watchdog (auto-abort after 30s of silence)
 * - Socket disconnect detection during active streams
 */

import { ref, readonly, watch } from 'vue'
import { useSocket } from './useSocket'

/** Debounce interval (ms) for flushing buffered tokens to the reactive ref. */
const TOKEN_FLUSH_INTERVAL = 50

/** If no streaming events arrive for this many ms, auto-abort the stream. */
const STREAM_ACTIVITY_TIMEOUT = 30_000

/**
 * Composable for streaming AI chat responses.
 *
 * @returns {Object} Reactive streaming state and control methods
 */
export function useStreaming() {
  const { on, off, initSocket, isConnected, isOnline } = useSocket()

  // Reactive state
  const streamingContent = ref('')
  const isStreaming = ref(false)
  const currentStreamId = ref(null)
  const currentConversationId = ref(null)
  const toolCalls = ref([])
  const streamError = ref(null)
  const processStep = ref('')

  // Agent orchestration state
  const agentPlan = ref([])
  const agentCurrentStep = ref(null)

  // Streaming error recovery state (Phase 13A.3)
  const partialContent = ref('')
  const canRetry = ref(false)
  const lastUserMessage = ref(null)

  // Internal token buffer — tokens accumulate here and are flushed
  // to the reactive `streamingContent` ref every TOKEN_FLUSH_INTERVAL ms
  // via requestAnimationFrame, preventing per-token re-renders.
  let _tokenBuffer = ''
  let _flushTimer = null
  let _rafId = null

  // Tool call timing
  let _toolStartTimes = {}

  // Stream activity watchdog timer
  let _activityTimer = null

  // Event handler references (for cleanup)
  let handlers = {}

  // --- Connection loss detection (two independent mechanisms) ---
  //
  // 1. Browser offline event (navigator.onLine → isOnline ref)
  //    Fires INSTANTLY when Wi-Fi is toggled off — no heartbeat delay.
  //
  // 2. Socket.IO disconnect event (isConnected ref)
  //    Fires when the Socket.IO transport detects the break — can take
  //    20-60s depending on ping interval and TCP keepalive settings.
  //
  // Both watchers call _abortStream() to unblock the hung UI.

  const _stopOnlineWatch = watch(isOnline, (online) => {
    if (!online && isStreaming.value) {
      _abortStream('Network connection lost while streaming. Please check your internet connection and try again.')
    }
  })

  const _stopDisconnectWatch = watch(isConnected, (connected) => {
    // Only abort if isStreaming is still true (the online watcher may
    // have already aborted it).
    if (!connected && isStreaming.value) {
      _abortStream('Connection lost while streaming. The response may have completed on the server — try refreshing the conversation.')
    }
  })

  /**
   * Abort an active stream with an error message.
   * Used by the watchdog timer and the disconnect watcher.
   */
  function _abortStream(errorMessage) {
    _clearActivityTimer()
    _immediateFlush()
    // Remove all event handlers FIRST — prevents any late-arriving backend
    // events (delivered after socket reconnects) from overwriting our state.
    _removeHandlers()
    isStreaming.value = false
    streamError.value = errorMessage
    canRetry.value = true

    if (streamingContent.value) {
      partialContent.value = streamingContent.value
    }
  }

  /**
   * Reset the activity watchdog timer.
   * Called on every incoming stream event to prove the stream is alive.
   */
  function _resetActivityTimer() {
    _clearActivityTimer()
    if (!isStreaming.value) return
    _activityTimer = setTimeout(() => {
      if (isStreaming.value) {
        console.warn('[AI Chatbot] Stream activity timeout — no events for', STREAM_ACTIVITY_TIMEOUT, 'ms')
        _abortStream('The response appears to have stalled. Please try again.')
      }
    }, STREAM_ACTIVITY_TIMEOUT)
  }

  function _clearActivityTimer() {
    if (_activityTimer !== null) {
      clearTimeout(_activityTimer)
      _activityTimer = null
    }
  }

  /**
   * Flush the internal token buffer to the reactive streamingContent ref
   * using requestAnimationFrame for smooth DOM updates.
   */
  function _flushTokenBuffer() {
    _flushTimer = null
    if (!_tokenBuffer) return

    const chunk = _tokenBuffer
    _tokenBuffer = ''

    // Use rAF to batch the reactive write with the next paint frame,
    // avoiding layout thrashing from rapid synchronous updates.
    _rafId = requestAnimationFrame(() => {
      streamingContent.value += chunk
      _rafId = null
    })
  }

  /**
   * Schedule a token buffer flush after TOKEN_FLUSH_INTERVAL ms.
   * If a flush is already pending, this is a no-op (the pending flush
   * will pick up all tokens accumulated so far).
   */
  function _scheduleFlush() {
    if (_flushTimer !== null) return
    _flushTimer = setTimeout(_flushTokenBuffer, TOKEN_FLUSH_INTERVAL)
  }

  /**
   * Immediately flush all pending tokens (used on stream end / error).
   */
  function _immediateFlush() {
    if (_flushTimer !== null) {
      clearTimeout(_flushTimer)
      _flushTimer = null
    }
    if (_rafId !== null) {
      cancelAnimationFrame(_rafId)
      _rafId = null
    }
    if (_tokenBuffer) {
      streamingContent.value += _tokenBuffer
      _tokenBuffer = ''
    }
  }

  /**
   * Start listening for streaming events for a specific conversation.
   * Must be called BEFORE sending the streaming message.
   *
   * @param {string} conversationId - The conversation to listen for
   */
  function startListening(conversationId) {
    // Ensure socket is connected
    initSocket()

    // Reset state
    streamingContent.value = ''
    isStreaming.value = false
    currentConversationId.value = conversationId
    currentStreamId.value = null
    toolCalls.value = []
    streamError.value = null
    processStep.value = ''
    agentPlan.value = []
    agentCurrentStep.value = null
    partialContent.value = ''
    canRetry.value = false

    // Reset internal buffer
    _tokenBuffer = ''
    if (_flushTimer !== null) {
      clearTimeout(_flushTimer)
      _flushTimer = null
    }
    if (_rafId !== null) {
      cancelAnimationFrame(_rafId)
      _rafId = null
    }
    _clearActivityTimer()
    _toolStartTimes = {}

    // Remove any previous handlers
    _removeHandlers()

    // Register event handlers
    handlers.onStreamStart = (data) => {
      if (data.conversation_id !== conversationId) return
      currentStreamId.value = data.stream_id
      isStreaming.value = true
      streamingContent.value = ''
      _tokenBuffer = ''
      toolCalls.value = []
      _resetActivityTimer()
    }

    handlers.onToken = (data) => {
      if (data.conversation_id !== conversationId) return
      // Buffer the token instead of writing directly to the reactive ref
      _tokenBuffer += data.content
      _scheduleFlush()
      _resetActivityTimer()
    }

    handlers.onToolCall = (data) => {
      if (data.conversation_id !== conversationId) return
      // Flush any pending tokens before showing tool indicator
      _immediateFlush()
      const callId = `${data.tool_name}_${toolCalls.value.length}`
      _toolStartTimes[callId] = Date.now()
      toolCalls.value.push({
        id: callId,
        name: data.tool_name,
        arguments: data.tool_arguments,
        status: 'executing',
        result: null,
        startTime: Date.now(),
        duration: null,
        summary: null,
      })
      _resetActivityTimer()
    }

    handlers.onToolResult = (data) => {
      if (data.conversation_id !== conversationId) return
      // Find the matching tool call and update it
      const tc = toolCalls.value.find(
        (t) => t.name === data.tool_name && t.status === 'executing'
      )
      if (tc) {
        tc.status = data.result?.error ? 'failed' : 'completed'
        tc.result = data.result
        tc.duration = Date.now() - (tc.startTime || Date.now())
        // Generate a brief summary from the result
        tc.summary = _summarizeToolResult(data.tool_name, data.result)
      }
      _resetActivityTimer()
    }

    handlers.onStreamEnd = (data) => {
      if (data.conversation_id !== conversationId) return
      // Flush any remaining buffered tokens immediately
      _immediateFlush()
      _clearActivityTimer()
      isStreaming.value = false
      canRetry.value = false
      partialContent.value = ''
      // Final content from server (authoritative)
      if (data.content) {
        streamingContent.value = data.content
      }
    }

    handlers.onError = (data) => {
      if (data.conversation_id !== conversationId) return
      // Flush any pending tokens so partial content is visible
      _immediateFlush()
      _clearActivityTimer()
      isStreaming.value = false
      streamError.value = data.error

      // Phase 13A.3: Preserve partial content for retry
      if (streamingContent.value) {
        partialContent.value = streamingContent.value
        canRetry.value = true
      } else {
        canRetry.value = true
      }
    }

    handlers.onProcessStep = (data) => {
      if (data.conversation_id !== conversationId) return
      processStep.value = data.step || ''
      _resetActivityTimer()
    }

    // Agent orchestration event handlers
    handlers.onAgentPlan = (data) => {
      if (data.conversation_id !== conversationId) return
      agentPlan.value = (data.plan || []).map(s => ({
        ...s,
        status: 'pending',
        summary: '',
        error: '',
      }))
      _resetActivityTimer()
    }

    handlers.onAgentStepStart = (data) => {
      if (data.conversation_id !== conversationId) return
      agentCurrentStep.value = data.step_id
      const step = agentPlan.value.find(s => s.step_id === data.step_id)
      if (step) {
        step.status = 'running'
      }
      _resetActivityTimer()
    }

    handlers.onAgentStepResult = (data) => {
      if (data.conversation_id !== conversationId) return
      const step = agentPlan.value.find(s => s.step_id === data.step_id)
      if (step) {
        step.status = data.status || 'completed'
        step.summary = data.summary || ''
        if (data.status === 'failed') {
          step.error = data.summary || 'Step failed'
        }
      }
      agentCurrentStep.value = null
      _resetActivityTimer()
    }

    on('ai_chat_stream_start', handlers.onStreamStart)
    on('ai_chat_token', handlers.onToken)
    on('ai_chat_tool_call', handlers.onToolCall)
    on('ai_chat_tool_result', handlers.onToolResult)
    on('ai_chat_stream_end', handlers.onStreamEnd)
    on('ai_chat_error', handlers.onError)
    on('ai_chat_process_step', handlers.onProcessStep)
    on('ai_chat_agent_plan', handlers.onAgentPlan)
    on('ai_chat_agent_step_start', handlers.onAgentStepStart)
    on('ai_chat_agent_step_result', handlers.onAgentStepResult)
  }

  /**
   * Stop listening for streaming events and clean up handlers.
   */
  function stopListening() {
    _removeHandlers()
    _immediateFlush()
    _clearActivityTimer()
    isStreaming.value = false
    currentStreamId.value = null
  }

  /**
   * Reset all streaming state (for starting a new message).
   */
  function reset() {
    _immediateFlush()
    _clearActivityTimer()
    streamingContent.value = ''
    toolCalls.value = []
    streamError.value = null
    processStep.value = ''
    currentStreamId.value = null
    isStreaming.value = false
    agentPlan.value = []
    agentCurrentStep.value = null
    partialContent.value = ''
    canRetry.value = false
    lastUserMessage.value = null
    _tokenBuffer = ''
    _toolStartTimes = {}
  }

  /**
   * Clean up the disconnect watcher when this composable is no longer needed.
   */
  function destroy() {
    stopListening()
    _stopOnlineWatch()
    _stopDisconnectWatch()
  }

  /**
   * Generate a brief human-readable summary from a tool result.
   * @param {string} toolName - The tool function name
   * @param {object} result - The tool result payload
   * @returns {string|null} A short summary string or null
   */
  function _summarizeToolResult(toolName, result) {
    if (!result) return null
    if (result.error) return `Error: ${typeof result.error === 'string' ? result.error.slice(0, 80) : 'execution failed'}`

    const data = result.data || result
    // Try common patterns
    if (data.total_records !== undefined) return `Retrieved ${data.total_records} records`
    if (data.count !== undefined) return `Found ${data.count} results`
    if (Array.isArray(data.records)) return `Retrieved ${data.records.length} records`
    if (Array.isArray(data.data)) return `Retrieved ${data.data.length} records`
    if (Array.isArray(data.rows)) return `Retrieved ${data.rows.length} rows`
    if (data.summary) return typeof data.summary === 'string' ? data.summary.slice(0, 80) : null
    if (data.message) return typeof data.message === 'string' ? data.message.slice(0, 80) : null
    return null
  }

  /**
   * Remove all registered event handlers.
   */
  function _removeHandlers() {
    if (handlers.onStreamStart) off('ai_chat_stream_start', handlers.onStreamStart)
    if (handlers.onToken) off('ai_chat_token', handlers.onToken)
    if (handlers.onToolCall) off('ai_chat_tool_call', handlers.onToolCall)
    if (handlers.onToolResult) off('ai_chat_tool_result', handlers.onToolResult)
    if (handlers.onStreamEnd) off('ai_chat_stream_end', handlers.onStreamEnd)
    if (handlers.onError) off('ai_chat_error', handlers.onError)
    if (handlers.onProcessStep) off('ai_chat_process_step', handlers.onProcessStep)
    if (handlers.onAgentPlan) off('ai_chat_agent_plan', handlers.onAgentPlan)
    if (handlers.onAgentStepStart) off('ai_chat_agent_step_start', handlers.onAgentStepStart)
    if (handlers.onAgentStepResult) off('ai_chat_agent_step_result', handlers.onAgentStepResult)
    handlers = {}
  }

  return {
    // Reactive state (readonly to prevent external mutation)
    streamingContent: readonly(streamingContent),
    isStreaming: readonly(isStreaming),
    currentStreamId: readonly(currentStreamId),
    toolCalls: readonly(toolCalls),
    streamError: readonly(streamError),
    processStep: readonly(processStep),

    // Agent orchestration state
    agentPlan: readonly(agentPlan),
    agentCurrentStep: readonly(agentCurrentStep),

    // Error recovery state (Phase 13A.3)
    partialContent: readonly(partialContent),
    canRetry: readonly(canRetry),

    // Methods
    startListening,
    stopListening,
    reset,
    destroy,
  }
}
