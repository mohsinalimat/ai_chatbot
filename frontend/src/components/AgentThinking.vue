<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<!--
  AgentThinking Component

  Displays the multi-agent orchestration plan and step-by-step progress.
  Shown during streaming when the orchestrator decomposes a complex query.
-->
<template>
  <div
    v-if="plan.length > 0"
    class="mb-3 border border-indigo-200 dark:border-indigo-800 rounded-lg overflow-hidden bg-indigo-50/50 dark:bg-indigo-900/20"
  >
    <!-- Header -->
    <button
      @click="isCollapsed = !isCollapsed"
      class="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-indigo-800 dark:text-indigo-300 hover:bg-indigo-100/50 dark:hover:bg-indigo-900/30 transition-colors"
    >
      <BrainCircuit :size="16" class="flex-shrink-0" />
      <span class="flex-1 text-left">
        {{ headerText }}
      </span>
      <span class="text-xs text-indigo-500 dark:text-indigo-400 mr-1">
        {{ completedCount }}/{{ plan.length }} steps
      </span>
      <ChevronDown
        :size="16"
        class="flex-shrink-0 transition-transform duration-200"
        :class="{ 'rotate-180': !isCollapsed }"
      />
    </button>

    <!-- Step List -->
    <div
      v-show="!isCollapsed"
      class="px-4 pb-3 space-y-1.5"
    >
      <div
        v-for="(step, index) in plan"
        :key="step.step_id"
        class="flex items-start gap-2.5 py-1.5"
      >
        <!-- Step Number -->
        <span
          class="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium"
          :class="stepNumberClass(step)"
        >
          <Check v-if="step.status === 'completed'" :size="12" />
          <X v-else-if="step.status === 'failed' || step.status === 'skipped'" :size="12" />
          <Loader2 v-else-if="step.status === 'running'" :size="12" class="animate-spin" />
          <span v-else>{{ index + 1 }}</span>
        </span>

        <!-- Step Content -->
        <div class="flex-1 min-w-0">
          <div
            class="text-sm"
            :class="stepTextClass(step)"
          >
            {{ step.description }}
          </div>
          <!-- Summary for completed steps -->
          <div
            v-if="step.status === 'completed' && step.summary"
            class="text-xs text-indigo-500 dark:text-indigo-400 mt-0.5 truncate"
          >
            {{ step.summary }}
          </div>
          <!-- Error for failed steps -->
          <div
            v-if="step.status === 'failed' && step.error"
            class="text-xs text-red-500 dark:text-red-400 mt-0.5 truncate"
          >
            {{ step.error }}
          </div>
        </div>

        <!-- Status label -->
        <span
          class="flex-shrink-0 text-xs"
          :class="stepStatusClass(step)"
        >
          {{ stepStatusText(step) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { BrainCircuit, ChevronDown, Check, X, Loader2 } from 'lucide-vue-next'

const props = defineProps({
  plan: {
    type: Array,
    default: () => [],
  },
  autoCollapse: {
    type: Boolean,
    default: false,
  },
})

const isCollapsed = ref(false)

// Auto-collapse when synthesis begins (parent sets autoCollapse=true)
watch(() => props.autoCollapse, (val) => {
  if (val) isCollapsed.value = true
})

const completedCount = computed(() =>
  props.plan.filter(s => s.status === 'completed').length
)

const isAllDone = computed(() =>
  props.plan.every(s => ['completed', 'failed', 'skipped'].includes(s.status))
)

const hasRunning = computed(() =>
  props.plan.some(s => s.status === 'running')
)

const headerText = computed(() => {
  if (isAllDone.value) return 'Analysis complete'
  if (hasRunning.value) return 'Analyzing your query...'
  return 'Planning analysis...'
})

const stepNumberClass = (step) => {
  switch (step.status) {
    case 'completed':
      return 'bg-green-500 text-white'
    case 'failed':
    case 'skipped':
      return 'bg-red-400 text-white'
    case 'running':
      return 'bg-indigo-500 text-white'
    default:
      return 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
  }
}

const stepTextClass = (step) => {
  switch (step.status) {
    case 'completed':
      return 'text-gray-600 dark:text-gray-400'
    case 'failed':
    case 'skipped':
      return 'text-gray-400 dark:text-gray-500 line-through'
    case 'running':
      return 'text-indigo-800 dark:text-indigo-200 font-medium'
    default:
      return 'text-gray-500 dark:text-gray-400'
  }
}

const stepStatusClass = (step) => {
  switch (step.status) {
    case 'completed':
      return 'text-green-600 dark:text-green-400'
    case 'failed':
      return 'text-red-500 dark:text-red-400'
    case 'skipped':
      return 'text-gray-400 dark:text-gray-500'
    case 'running':
      return 'text-indigo-600 dark:text-indigo-400'
    default:
      return 'text-gray-400 dark:text-gray-500'
  }
}

const stepStatusText = (step) => {
  switch (step.status) {
    case 'completed': return 'Done'
    case 'failed': return 'Failed'
    case 'skipped': return 'Skipped'
    case 'running': return 'Running...'
    default: return 'Pending'
  }
}
</script>
