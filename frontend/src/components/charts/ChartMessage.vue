<template>
  <div class="mt-4 border border-gray-200 rounded-lg overflow-hidden">
    <EChartRenderer :option="echartOption" :height="320" />
    <div class="px-3 py-2 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
      <span class="text-xs text-gray-500 flex items-center gap-1">
        <BarChart3 :size="14" />
        Interactive Chart
      </span>
      <button
        v-if="rawData"
        @click="showData = !showData"
        class="text-xs text-blue-600 hover:text-blue-800 transition-colors"
      >
        {{ showData ? 'Hide data' : 'Show data' }}
      </button>
    </div>
    <div v-if="showData && rawData" class="px-3 py-2 bg-gray-50 border-t border-gray-100">
      <pre class="text-xs text-gray-600 overflow-x-auto max-h-48 overflow-y-auto">{{ JSON.stringify(rawData, null, 2) }}</pre>
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
