<template>
  <div ref="chartContainer" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script setup>
import { ref, shallowRef, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  option: {
    type: Object,
    required: true,
  },
  height: {
    type: Number,
    default: 320,
  },
})

const chartContainer = ref(null)
const chartInstance = shallowRef(null)
let resizeObserver = null

onMounted(async () => {
  if (!chartContainer.value) return

  // Lazy-load echarts to avoid blocking initial page load
  const echarts = await import('echarts')
  const chart = echarts.init(chartContainer.value)
  chartInstance.value = chart

  chart.setOption(props.option)

  // Watch for container resize
  resizeObserver = new ResizeObserver(() => {
    chart.resize()
  })
  resizeObserver.observe(chartContainer.value)
})

// Re-render when option prop changes
watch(
  () => props.option,
  (newOption) => {
    if (chartInstance.value && newOption) {
      chartInstance.value.setOption(newOption, true)
    }
  },
  { deep: true }
)

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chartInstance.value) {
    chartInstance.value.dispose()
    chartInstance.value = null
  }
})
</script>
