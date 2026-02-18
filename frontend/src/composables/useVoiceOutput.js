/**
 * Voice Output Composable
 *
 * Provides text-to-speech functionality using the Web Speech API
 * (SpeechSynthesis). Strips markdown before speaking.
 *
 * Browser support: All modern browsers support SpeechSynthesis.
 *
 * Note on autoplay policy: Chrome requires a user gesture before
 * speechSynthesis.speak() will work. Call warmup() during a click
 * handler (e.g., when user starts voice recording) to unlock the
 * synthesis engine for subsequent programmatic speak() calls.
 */
import { ref, readonly, onUnmounted } from 'vue'

export function useVoiceOutput() {
  const isSpeaking = ref(false)
  const isSupported = ref(typeof window !== 'undefined' && 'speechSynthesis' in window)

  let currentUtterance = null
  let warmedUp = false

  /**
   * Strip markdown formatting from text for cleaner speech.
   */
  function stripMarkdown(text) {
    return text
      .replace(/#{1,6}\s+/g, '') // Headers
      .replace(/\*\*(.+?)\*\*/g, '$1') // Bold
      .replace(/\*(.+?)\*/g, '$1') // Italic
      .replace(/__(.+?)__/g, '$1') // Bold alt
      .replace(/_(.+?)_/g, '$1') // Italic alt
      .replace(/`{1,3}[^`]*`{1,3}/g, '') // Code blocks
      .replace(/!\[.*?\]\(.*?\)/g, '') // Images
      .replace(/\[(.+?)\]\(.*?\)/g, '$1') // Links (keep text)
      .replace(/^\s*[-*+]\s+/gm, '') // List markers
      .replace(/^\s*\d+\.\s+/gm, '') // Numbered lists
      .replace(/^\s*>\s+/gm, '') // Blockquotes
      .replace(/\|[^|]*\|/g, '') // Table cells
      .replace(/[-]{3,}/g, '') // Horizontal rules
      .replace(/\n{2,}/g, '. ') // Multiple newlines to pause
      .replace(/\n/g, ' ') // Single newlines to space
      .trim()
  }

  /**
   * Warm up the SpeechSynthesis engine during a user gesture.
   * This unlocks programmatic speak() calls in Chrome and other
   * browsers that enforce autoplay policies on TTS.
   * Call this from a click handler (e.g., mic button click).
   */
  function warmup() {
    if (!isSupported.value || warmedUp) return
    const silent = new SpeechSynthesisUtterance('')
    silent.volume = 0
    window.speechSynthesis.speak(silent)
    warmedUp = true
  }

  function speak(text) {
    if (!isSupported.value) return

    // Stop any current speech
    stop()

    const cleanText = stripMarkdown(text)
    if (!cleanText) return

    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utterance.lang = navigator.language || 'en-US'

    utterance.onstart = () => {
      isSpeaking.value = true
    }

    utterance.onend = () => {
      isSpeaking.value = false
      currentUtterance = null
    }

    utterance.onerror = (event) => {
      // 'interrupted' and 'canceled' are expected when stop() is called
      if (event.error !== 'interrupted' && event.error !== 'canceled') {
        console.warn('SpeechSynthesis error:', event.error)
      }
      isSpeaking.value = false
      currentUtterance = null
    }

    currentUtterance = utterance
    window.speechSynthesis.speak(utterance)
  }

  function stop() {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
    isSpeaking.value = false
    currentUtterance = null
  }

  function toggle(text) {
    if (isSpeaking.value) {
      stop()
    } else {
      speak(text)
    }
  }

  onUnmounted(() => {
    stop()
  })

  return {
    isSpeaking: readonly(isSpeaking),
    isSupported: readonly(isSupported),
    speak,
    stop,
    toggle,
    warmup,
  }
}
