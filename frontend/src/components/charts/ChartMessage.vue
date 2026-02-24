<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<template>
  <div class="mt-4 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
    <EChartRenderer :option="echartOption" :height="320" />
    <div class="px-3 py-2 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
      <span class="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
        <BarChart3 :size="14" />
        Interactive Chart
      </span>
      <button
        v-if="rawData"
        @click="showData = !showData"
        class="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
      >
        {{ showData ? 'Hide data' : 'Show data' }}
      </button>
    </div>
    <div v-if="showData && rawData" class="px-3 py-2 bg-gray-50 dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700">
      <pre class="text-xs text-gray-600 dark:text-gray-300 overflow-x-auto max-h-48 overflow-y-auto">{{ JSON.stringify(rawData, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { BarChart3 } from 'lucide-vue-next'
import EChartRenderer from './EChartRenderer.vue'

defineProps({
  echartOption: {
    type: Object,
    required: true,
  },
  rawData: {
    type: [Object, Array],
    default: null,
  },
})

const showData = ref(false)
</script>
