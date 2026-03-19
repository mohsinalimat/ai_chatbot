// Copyright (c) 2026, Sanjay Kumar and contributors
// For license information, please see license.txt
/**
 * Voice Input Composable
 *
 * Provides speech-to-text functionality using the Web Speech API
 * (SpeechRecognition / webkitSpeechRecognition).
 *
 * Browser support: Chrome, Edge, Safari 14.1+. Firefox does NOT support it.
 * Falls back gracefully with isSupported = false.
 *
 * Options:
 *   autoSendDelay (ms) — after the user stops speaking for this duration
 *     (no new final results), the composable sets `silenceTimeout` to true,
 *     signalling the consumer to auto-submit. Set to 0 to disable. Default: 2000.
 */
import { ref, readonly, onUnmounted } from 'vue'

export function useVoiceInput(options = {}) {
  const { autoSendDelay = 2000 } = options

  const isListening = ref(false)
  const transcript = ref('')
  const interimTranscript = ref('')
  const error = ref(null)
  const silenceTimeout = ref(false)
  const language = ref(localStorage.getItem('ai_chatbot_voice_lang') || '')

  // Feature detection
  const SpeechRecognitionAPI =
    typeof window !== 'undefined'
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null
  const isSupported = ref(!!SpeechRecognitionAPI)

  let recognition = null
  let silenceTimer = null

  function _resetSilenceTimer() {
    if (silenceTimer) {
      clearTimeout(silenceTimer)
      silenceTimer = null
    }
    silenceTimeout.value = false
  }

  function _startSilenceTimer() {
    _resetSilenceTimer()
    if (autoSendDelay <= 0) return
    silenceTimer = setTimeout(() => {
      // Only fire if we have actual transcript content and are still listening
      if (isListening.value && transcript.value.trim()) {
        silenceTimeout.value = true
      }
    }, autoSendDelay)
  }

  function startListening() {
    if (!SpeechRecognitionAPI) {
      error.value = 'Speech recognition is not supported in this browser. Use Chrome, Edge, or Safari.'
      return
    }

    // Reset state
    error.value = null
    transcript.value = ''
    interimTranscript.value = ''
    silenceTimeout.value = false
    _resetSilenceTimer()

    recognition = new SpeechRecognitionAPI()
    recognition.continuous = true // Keep listening until stopped
    recognition.interimResults = true // Show interim results for feedback
    recognition.lang = language.value || navigator.language || 'en-US'

    recognition.onstart = () => {
      isListening.value = true
    }

    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''

      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          finalText += result[0].transcript
        } else {
          interimText += result[0].transcript
        }
      }

      transcript.value = finalText
      interimTranscript.value = interimText

      // Reset silence timer on every result (speech is ongoing).
      // Start a new timer only when we have final text — after final
      // results arrive and no more follow within autoSendDelay, we
      // fire the silence timeout.
      if (finalText) {
        _startSilenceTimer()
      } else {
        // Interim results mean user is still speaking
        _resetSilenceTimer()
      }
    }

    recognition.onerror = (event) => {
      // 'no-speech' is not a real error, just silence
      if (event.error === 'no-speech') return

      error.value = `Speech recognition error: ${event.error}`
      isListening.value = false
      _resetSilenceTimer()
    }

    recognition.onend = () => {
      isListening.value = false
      _resetSilenceTimer()
      // Merge any remaining interim into final
      if (interimTranscript.value) {
        transcript.value += interimTranscript.value
        interimTranscript.value = ''
      }
    }

    try {
      recognition.start()
    } catch (e) {
      error.value = `Could not start microphone: ${e.message}`
      isListening.value = false
    }
  }

  function stopListening() {
    _resetSilenceTimer()
    if (recognition) {
      recognition.stop()
      recognition = null
    }
    isListening.value = false
  }

  function resetTranscript() {
    transcript.value = ''
    interimTranscript.value = ''
    error.value = null
    silenceTimeout.value = false
  }

  function setLanguage(lang) {
    language.value = lang
    localStorage.setItem('ai_chatbot_voice_lang', lang)
  }

  // Clean up on component unmount
  onUnmounted(() => {
    _resetSilenceTimer()
    if (recognition) {
      recognition.abort()
      recognition = null
    }
  })

  return {
    isListening: readonly(isListening),
    transcript: readonly(transcript),
    interimTranscript: readonly(interimTranscript),
    error: readonly(error),
    isSupported: readonly(isSupported),
    silenceTimeout: readonly(silenceTimeout),
    language: readonly(language),
    startListening,
    stopListening,
    resetTranscript,
    setLanguage,
  }
}
