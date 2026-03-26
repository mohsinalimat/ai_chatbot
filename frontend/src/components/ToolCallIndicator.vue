<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<!--
  ToolCallIndicator — Phase 13A.2

  Displays tool execution progress during streaming. Each tool call shows:
  - Tool name (human-readable)
  - Status: executing (spinner), completed (checkmark), failed (x-mark)
  - Duration (once completed)
  - Brief summary of result (e.g. "Retrieved 24 records")

  Multiple tool calls are stacked vertically.
  The entire block is collapsible via a header toggle.
-->
<template>
  <div v-if="tools.length > 0" class="mb-3 space-y-1.5">
    <!-- Header with collapse toggle -->
    <button
      @click="collapsed = !collapsed"
      class="flex items-center gap-1.5 text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
    >
      <svg
        class="w-3 h-3 transition-transform duration-200"
        :class="{ '-rotate-90': collapsed }"
        fill="none" stroke="currentColor" viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
      <Wrench :size="12" />
      <span>
        {{ completedCount }}/{{ tools.length }} tool{{ tools.length !== 1 ? 's' : '' }}
        {{ allDone ? 'completed' : 'running' }}
      </span>
    </button>

    <!-- Tool call list -->
    <div v-show="!collapsed" class="space-y-1.5">
      <div
        v-for="tc in tools"
        :key="tc.id || tc.name"
        class="flex items-start gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors duration-200"
        :class="statusBg(tc.status)"
      >
        <!-- Status icon -->
        <div class="flex-shrink-0 mt-0.5">
          <!-- Executing: spinner -->
          <div
            v-if="tc.status === 'executing'"
            class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
          ></div>
          <!-- Completed: checkmark -->
          <svg
            v-else-if="tc.status === 'completed'"
            class="w-4 h-4 text-green-600 dark:text-green-400"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <!-- Failed: x-mark -->
          <svg
            v-else-if="tc.status === 'failed'"
            class="w-4 h-4 text-red-500 dark:text-red-400"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>

        <!-- Tool info -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="font-medium" :class="statusText(tc.status)">
              {{ formatToolName(tc.name) }}
            </span>
            <span v-if="tc.status === 'executing'" class="text-blue-400 dark:text-blue-500 animate-pulse">...</span>
            <!-- Duration badge -->
            <span
              v-if="tc.duration != null && tc.status !== 'executing'"
              class="text-xs text-gray-400 dark:text-gray-500 tabular-nums"
            >
              {{ formatDuration(tc.duration) }}
            </span>
          </div>
          <!-- Summary line -->
          <div
            v-if="tc.summary && tc.status !== 'executing'"
            class="text-xs mt-0.5"
            :class="tc.status === 'failed' ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'"
          >
            {{ tc.summary }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Wrench } from 'lucide-vue-next'

const props = defineProps({
  tools: {
    type: Array,
    required: true,
    default: () => [],
  },
})

const collapsed = ref(false)

const completedCount = computed(() =>
  props.tools.filter(t => t.status === 'completed' || t.status === 'failed').length
)

const allDone = computed(() =>
  props.tools.length > 0 && props.tools.every(t => t.status !== 'executing')
)

/**
 * Format a tool function name for display.
 * "get_sales_analytics" → "Sales Analytics"
 */
function formatToolName(name) {
  if (!name) return 'Tool'
  return name
    .replace(/^(get_|search_|list_|create_|update_|delete_|execute_|run_)/, '')
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/**
 * Format duration in milliseconds to a human string.
 */
function formatDuration(ms) {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/**
 * Background class based on tool status.
 */
function statusBg(status) {
  switch (status) {
    case 'executing':
      return 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50'
    case 'completed':
      return 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800/50'
    case 'failed':
      return 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50'
    default:
      return 'bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
  }
}

/**
 * Text colour class based on tool status.
 */
function statusText(status) {
  switch (status) {
    case 'executing': return 'text-blue-800 dark:text-blue-300'
    case 'completed': return 'text-green-800 dark:text-green-300'
    case 'failed': return 'text-red-800 dark:text-red-300'
    default: return 'text-gray-800 dark:text-gray-300'
  }
}
</script>
