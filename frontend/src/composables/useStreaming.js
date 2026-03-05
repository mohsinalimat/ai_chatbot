// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt
/**
 * Streaming Composable
 *
 * Manages real-time AI response streaming via Frappe's Socket.IO realtime events.
 * Listens for token chunks, tool calls, and stream lifecycle events.
 */

import { ref, readonly } from 'vue'
import { useSocket } from './useSocket'

/**
 * Composable for streaming AI chat responses.
 *
 * @returns {Object} Reactive streaming state and control methods
 */
export function useStreaming() {
  const { on, off, initSocket } = useSocket()

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

  // Event handler references (for cleanup)
  let handlers = {}

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

    // Remove any previous handlers
    _removeHandlers()

    // Register event handlers
    handlers.onStreamStart = (data) => {
      if (data.conversation_id !== conversationId) return
      currentStreamId.value = data.stream_id
      isStreaming.value = true
      streamingContent.value = ''
      toolCalls.value = []
    }

    handlers.onToken = (data) => {
      if (data.conversation_id !== conversationId) return
      streamingContent.value += data.content
    }

    handlers.onToolCall = (data) => {
      if (data.conversation_id !== conversationId) return
      toolCalls.value.push({
        name: data.tool_name,
        arguments: data.tool_arguments,
        status: 'executing',
        result: null,
      })
    }

    handlers.onToolResult = (data) => {
      if (data.conversation_id !== conversationId) return
      // Find the matching tool call and update it
      const tc = toolCalls.value.find(
        (t) => t.name === data.tool_name && t.status === 'executing'
      )
      if (tc) {
        tc.status = 'completed'
        tc.result = data.result
      }
    }

    handlers.onStreamEnd = (data) => {
      if (data.conversation_id !== conversationId) return
      isStreaming.value = false
      // Final content from server (authoritative)
      if (data.content) {
        streamingContent.value = data.content
      }
    }

    handlers.onError = (data) => {
      if (data.conversation_id !== conversationId) return
      isStreaming.value = false
      streamError.value = data.error
    }

    handlers.onProcessStep = (data) => {
      if (data.conversation_id !== conversationId) return
      processStep.value = data.step || ''
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
    }

    handlers.onAgentStepStart = (data) => {
      if (data.conversation_id !== conversationId) return
      agentCurrentStep.value = data.step_id
      const step = agentPlan.value.find(s => s.step_id === data.step_id)
      if (step) {
        step.status = 'running'
      }
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
    isStreaming.value = false
    currentStreamId.value = null
  }

  /**
   * Reset all streaming state (for starting a new message).
   */
  function reset() {
    streamingContent.value = ''
    toolCalls.value = []
    streamError.value = null
    processStep.value = ''
    currentStreamId.value = null
    isStreaming.value = false
    agentPlan.value = []
    agentCurrentStep.value = null
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

    // Methods
    startListening,
    stopListening,
    reset,
  }
}
