// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt
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

  /**
   * Get the preferred voice language from localStorage (shared with useVoiceInput).
   * Falls back to navigator.language then 'en-US'.
   */
  function getPreferredLang() {
    return localStorage.getItem('ai_chatbot_voice_lang') || navigator.language || 'en-US'
  }

  /**
   * Find the best SpeechSynthesisVoice matching a BCP-47 language code.
   * Tries exact match first (e.g. "hi-IN"), then prefix match (e.g. "hi").
   */
  function findVoice(lang) {
    const voices = window.speechSynthesis.getVoices()
    if (!voices.length || !lang) return null
    // Exact match
    const exact = voices.find(v => v.lang === lang)
    if (exact) return exact
    // Prefix match (e.g. "hi-IN" matches voice with lang "hi")
    const prefix = lang.split('-')[0]
    return voices.find(v => v.lang.startsWith(prefix)) || null
  }

  function speak(text) {
    if (!isSupported.value) return

    // Stop any current speech
    stop()

    const cleanText = stripMarkdown(text)
    if (!cleanText) return

    const lang = getPreferredLang()
    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utterance.lang = lang

    // Try to assign a voice matching the selected language
    const voice = findVoice(lang)
    if (voice) {
      utterance.voice = voice
    }

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
