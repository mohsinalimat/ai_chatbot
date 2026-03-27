<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<!--
  ConfirmationCard.vue — Phase 13B

  Rendered inside ChatMessage when the AI proposes a write operation.
  Shows a structured preview of the action with Confirm/Cancel buttons.

  Visual states: pending, processing, success, declined, error
-->
<template>
  <div
    class="mt-3 rounded-lg border overflow-hidden"
    :class="cardBorderClass"
  >
    <!-- Header -->
    <div
      class="flex items-center gap-2 px-4 py-2.5"
      :class="cardHeaderClass"
    >
      <component :is="actionIcon" :size="16" class="flex-shrink-0" />
      <span class="text-sm font-medium">{{ headerText }}</span>
      <span
        v-if="state !== 'pending'"
        class="ml-auto text-xs font-medium px-2 py-0.5 rounded-full"
        :class="badgeClass"
      >
        {{ badgeText }}
      </span>
    </div>

    <!-- Body -->
    <div class="px-4 py-3 bg-white dark:bg-gray-800">
      <!-- Display Fields -->
      <div v-if="displayFields.length" class="space-y-2">
        <div
          v-for="field in displayFields"
          :key="field.fieldname"
          class="flex items-start gap-2 text-sm"
        >
          <span class="text-gray-500 dark:text-gray-400 min-w-[120px] flex-shrink-0">
            {{ field.label }}
          </span>
          <span class="text-gray-800 dark:text-gray-200 font-medium">
            <!-- Update diff: show old → new -->
            <template v-if="field.old_value !== undefined && field.old_value !== field.value">
              <span class="line-through text-gray-400 dark:text-gray-500 mr-1">{{ formatValue(field.old_value, field.fieldtype) }}</span>
              <span>{{ formatValue(field.value, field.fieldtype) }}</span>
            </template>
            <template v-else>
              {{ formatValue(field.value, field.fieldtype) }}
            </template>
          </span>
        </div>
      </div>

      <!-- Child Tables -->
      <div v-for="table in childTables" :key="table.fieldname" class="mt-3">
        <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
          {{ table.label }}
          <span v-if="table.total_rows > table.rows.length" class="font-normal normal-case">
            (showing {{ table.rows.length }} of {{ table.total_rows }})
          </span>
        </div>
        <div class="overflow-x-auto rounded border border-gray-200 dark:border-gray-600">
          <table class="min-w-full text-xs">
            <thead>
              <tr class="bg-gray-50 dark:bg-gray-700">
                <th
                  v-for="col in table.columns"
                  :key="col.fieldname"
                  class="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-300"
                >
                  {{ col.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in table.rows"
                :key="idx"
                class="border-t border-gray-100 dark:border-gray-700"
              >
                <td
                  v-for="col in table.columns"
                  :key="col.fieldname"
                  class="px-2 py-1.5 text-gray-700 dark:text-gray-300"
                >
                  {{ formatValue(row[col.fieldname], col.fieldtype) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Warnings -->
      <div
        v-if="warnings.length && state === 'pending'"
        class="mt-3 p-2.5 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700"
      >
        <div v-for="(warning, idx) in warnings" :key="idx" class="flex items-start gap-1.5 text-xs text-amber-800 dark:text-amber-300">
          <AlertTriangle :size="12" class="flex-shrink-0 mt-0.5" />
          <span>{{ warning }}</span>
        </div>
      </div>

      <!-- Errors -->
      <div
        v-if="errors.length"
        class="mt-3 p-2.5 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700"
      >
        <div v-for="(error, idx) in errors" :key="idx" class="flex items-start gap-1.5 text-xs text-red-700 dark:text-red-300">
          <XCircle :size="12" class="flex-shrink-0 mt-0.5" />
          <span>{{ error }}</span>
        </div>
      </div>

      <!-- Success result -->
      <div v-if="state === 'success' && resultData" class="mt-3 p-2.5 rounded-md bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700">
        <div class="flex items-center gap-1.5 text-sm text-green-800 dark:text-green-300">
          <CheckCircle2 :size="14" class="flex-shrink-0" />
          <span>{{ resultData.message || `${doctype} created successfully` }}</span>
        </div>
        <a
          v-if="resultData.doc_url"
          :href="resultData.doc_url"
          target="_blank"
          class="inline-flex items-center gap-1 mt-1.5 text-xs text-green-700 dark:text-green-400 hover:underline"
        >
          <ExternalLink :size="12" />
          Open {{ resultData.name || doctype }}
        </a>
      </div>

      <!-- Error result -->
      <div v-if="state === 'error' && errorMessage" class="mt-3 p-2.5 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700">
        <div class="flex items-start gap-1.5 text-sm text-red-700 dark:text-red-300">
          <XCircle :size="14" class="flex-shrink-0 mt-0.5" />
          <span>{{ errorMessage }}</span>
        </div>
      </div>
    </div>

    <!-- Actions footer -->
    <div
      v-if="state === 'pending' || state === 'processing'"
      class="flex items-center justify-end gap-2 px-4 py-2.5 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
    >
      <button
        :disabled="state === 'processing'"
        class="px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        @click="handleCancel"
      >
        Cancel
      </button>
      <button
        :disabled="state === 'processing' || errors.length > 0"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :class="confirmButtonClass"
        @click="handleConfirm"
      >
        <Loader2 v-if="state === 'processing'" :size="12" class="animate-spin" />
        <component v-else :is="confirmButtonIcon" :size="12" />
        {{ confirmButtonText }}
      </button>
    </div>

    <!-- Undo footer (success state with undo available) -->
    <div
      v-if="state === 'success' && undoToken && !undoExpired && !undoExecuted"
      class="flex items-center justify-end gap-2 px-4 py-2 border-t border-green-200 dark:border-green-700 bg-green-50/50 dark:bg-green-900/10"
    >
      <button
        :disabled="undoProcessing"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-amber-700 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-300 bg-white dark:bg-gray-700 border border-amber-300 dark:border-amber-600 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        @click="handleUndo"
      >
        <Loader2 v-if="undoProcessing" :size="12" class="animate-spin" />
        <Undo2 v-else :size="12" />
        Undo ({{ undoCountdown }})
      </button>
    </div>

    <!-- Undo executed notice -->
    <div
      v-if="undoExecuted"
      class="flex items-center gap-1.5 px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500 dark:text-gray-400"
    >
      <Undo2 :size="12" />
      Action undone successfully.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  FilePlus, FileEdit, FileCheck, FileX2,
  AlertTriangle, XCircle, CheckCircle2, ExternalLink,
  Loader2, Undo2
} from 'lucide-vue-next'
import { chatAPI } from '../utils/api'

const props = defineProps({
  confirmationId: { type: String, required: true },
  action: { type: String, required: true },
  doctype: { type: String, required: true },
  name: { type: String, default: null },
  displayFields: { type: Array, default: () => [] },
  childTables: { type: Array, default: () => [] },
  warnings: { type: Array, default: () => [] },
  errors: { type: Array, default: () => [] },
  isSubmittable: { type: Boolean, default: false },
  // Pre-populated from persisted confirmation_state (page reload)
  initialState: { type: String, default: 'pending' },
  initialResult: { type: Object, default: null },
  initialUndoToken: { type: String, default: null },
  initialUndoExpires: { type: String, default: null },
})

const emit = defineEmits(['confirmed', 'cancelled'])

// State machine: pending → processing → success/error/declined
const state = ref(props.initialState)
const resultData = ref(props.initialResult)
const errorMessage = ref(null)
const undoToken = ref(props.initialUndoToken)
const undoExpires = ref(props.initialUndoExpires)
const undoProcessing = ref(false)
const undoExecuted = ref(false)

// Countdown timer for undo
const undoSecondsLeft = ref(0)
let countdownInterval = null

const undoExpired = computed(() => undoSecondsLeft.value <= 0)

const undoCountdown = computed(() => {
  const s = undoSecondsLeft.value
  if (s <= 0) return '0:00'
  const min = Math.floor(s / 60)
  const sec = s % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
})

function startUndoCountdown() {
  if (!undoExpires.value) return
  const updateCountdown = () => {
    const now = Date.now()
    const expires = new Date(undoExpires.value).getTime()
    undoSecondsLeft.value = Math.max(0, Math.floor((expires - now) / 1000))
    if (undoSecondsLeft.value <= 0 && countdownInterval) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }
  updateCountdown()
  countdownInterval = setInterval(updateCountdown, 1000)
}

onMounted(() => {
  if (state.value === 'success' && undoToken.value) {
    startUndoCountdown()
  }
})

onUnmounted(() => {
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }
})

// Action-dependent UI
const actionIcon = computed(() => {
  switch (props.action) {
    case 'create': return FilePlus
    case 'update': return FileEdit
    case 'submit': return FileCheck
    case 'cancel': return FileX2
    default: return FilePlus
  }
})

const headerText = computed(() => {
  const labels = {
    create: `Create ${props.doctype}`,
    update: `Update ${props.doctype}`,
    submit: `Submit ${props.doctype}`,
    cancel: `Cancel ${props.doctype}`,
  }
  let text = labels[props.action] || `${props.action} ${props.doctype}`
  if (props.name) text += ` — ${props.name}`
  return text
})

const confirmButtonText = computed(() => {
  if (state.value === 'processing') return 'Processing...'
  switch (props.action) {
    case 'create': return props.isSubmittable ? 'Create Draft' : 'Save'
    case 'update': return 'Update'
    case 'submit': return 'Submit'
    case 'cancel': return 'Cancel Document'
    default: return 'Confirm'
  }
})

const confirmButtonIcon = computed(() => {
  switch (props.action) {
    case 'create': return FilePlus
    case 'update': return FileEdit
    case 'submit': return FileCheck
    case 'cancel': return FileX2
    default: return CheckCircle2
  }
})

const confirmButtonClass = computed(() => {
  if (props.action === 'cancel') return 'bg-red-600 hover:bg-red-700'
  if (props.action === 'submit') return 'bg-amber-600 hover:bg-amber-700'
  return 'bg-blue-600 hover:bg-blue-700'
})

const cardBorderClass = computed(() => {
  switch (state.value) {
    case 'success': return 'border-green-300 dark:border-green-700'
    case 'error': return 'border-red-300 dark:border-red-700'
    case 'declined': return 'border-gray-300 dark:border-gray-600 opacity-60'
    default: return 'border-blue-200 dark:border-blue-700'
  }
})

const cardHeaderClass = computed(() => {
  switch (state.value) {
    case 'success': return 'bg-green-50 dark:bg-green-900/30 text-green-800 dark:text-green-300'
    case 'error': return 'bg-red-50 dark:bg-red-900/30 text-red-800 dark:text-red-300'
    case 'declined': return 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
    default: return 'bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
  }
})

const badgeClass = computed(() => {
  switch (state.value) {
    case 'success': return 'bg-green-100 dark:bg-green-800/40 text-green-700 dark:text-green-300'
    case 'error': return 'bg-red-100 dark:bg-red-800/40 text-red-700 dark:text-red-300'
    case 'declined': return 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
    default: return ''
  }
})

const badgeText = computed(() => {
  switch (state.value) {
    case 'success': return undoExecuted.value ? 'Undone' : 'Confirmed'
    case 'error': return 'Failed'
    case 'declined': return 'Cancelled'
    default: return ''
  }
})

// Value formatting
function formatValue(value, fieldtype) {
  if (value === null || value === undefined || value === '') return '—'
  if (fieldtype === 'Currency' || fieldtype === 'Float') {
    const num = Number(value)
    return isNaN(num) ? value : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  if (fieldtype === 'Int') {
    const num = Number(value)
    return isNaN(num) ? value : num.toLocaleString('en-US')
  }
  if (fieldtype === 'Check') return value ? 'Yes' : 'No'
  return String(value)
}

// Handlers
async function handleConfirm() {
  if (state.value !== 'pending' || props.errors.length > 0) return
  state.value = 'processing'

  try {
    const result = await chatAPI.confirmAction(props.confirmationId)
    if (result.success) {
      state.value = 'success'
      resultData.value = result
      undoToken.value = result.undo_token || null
      undoExpires.value = result.undo_expires || null
      if (undoToken.value) startUndoCountdown()
      emit('confirmed', result)
    } else {
      state.value = 'error'
      errorMessage.value = result.error || 'Action failed.'
    }
  } catch (err) {
    state.value = 'error'
    errorMessage.value = err.message || 'An unexpected error occurred.'
  }
}

async function handleCancel() {
  if (state.value !== 'pending') return
  state.value = 'declined'

  try {
    await chatAPI.cancelAction(props.confirmationId)
  } catch (err) {
    console.error('Cancel action error:', err)
  }

  emit('cancelled', { confirmationId: props.confirmationId, action: props.action, doctype: props.doctype })
}

async function handleUndo() {
  if (!undoToken.value || undoProcessing.value || undoExpired.value) return
  undoProcessing.value = true

  try {
    const result = await chatAPI.undoAction(undoToken.value)
    if (result.success) {
      undoExecuted.value = true
      if (countdownInterval) {
        clearInterval(countdownInterval)
        countdownInterval = null
      }
    } else {
      errorMessage.value = result.error || 'Undo failed.'
    }
  } catch (err) {
    errorMessage.value = err.message || 'Undo failed.'
  } finally {
    undoProcessing.value = false
  }
}
</script>
