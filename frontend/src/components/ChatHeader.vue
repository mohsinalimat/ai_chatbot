<template>
  <div class="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-4 shadow-md">
    <div class="flex items-center gap-4">
      <!-- Sidebar Toggle (extreme left, outside centered content) -->
      <button
        @click="$emit('toggle-sidebar')"
        class="p-2 bg-blue-500 hover:bg-blue-400 rounded-lg transition-colors flex-shrink-0"
        :title="sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'"
      >
        <PanelLeftOpen v-if="sidebarCollapsed" :size="20" />
        <PanelLeftClose v-else :size="20" />
      </button>

      <!-- Centered header content -->
      <div class="flex-1 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <Bot :size="32" />
          <div>
            <h1 class="text-xl font-bold">ERPNext AI Assistant</h1>
            <p class="text-sm text-blue-100">Powered by {{ selectedProvider }}</p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <!-- Provider Selector -->
          <div class="relative">
            <button
              @click="dropdownOpen = !dropdownOpen"
              class="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-400 rounded-lg transition-colors"
            >
              <Cpu :size="16" />
              <span>{{ selectedProvider }}</span>
              <ChevronDown v-if="!dropdownOpen" :size="16" />
              <ChevronUp v-else :size="16" />
            </button>

            <!-- Dropdown Menu -->
            <div
              v-if="dropdownOpen"
              class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg py-1 z-50"
            >
              <button
                v-for="option in providerOptions"
                :key="option.value"
                @click="selectProvider(option.value)"
                class="w-full px-4 py-2 text-left text-gray-700 hover:bg-blue-50 transition-colors"
              >
                {{ option.label }}
              </button>
            </div>
          </div>

          <!-- Settings Button -->
          <button
            @click="openSettings"
            class="p-2 bg-blue-500 hover:bg-blue-400 rounded-lg transition-colors"
          >
            <Settings :size="20" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Bot, Cpu, Settings, ChevronDown, ChevronUp, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'

const props = defineProps({
  provider: {
    type: String,
    default: 'OpenAI',
  },
  sidebarCollapsed: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:provider', 'toggle-sidebar'])

const selectedProvider = ref(props.provider)
const dropdownOpen = ref(false)

const providerOptions = [
  { label: 'OpenAI', value: 'OpenAI' },
  { label: 'Claude', value: 'Claude' },
]

const selectProvider = (value) => {
  selectedProvider.value = value
  dropdownOpen.value = false
  emit('update:provider', value)
}

const openSettings = () => {
  window.open('/app/chatbot-settings', '_blank')
}

watch(selectedProvider, (newValue) => {
  emit('update:provider', newValue)
})
</script>
