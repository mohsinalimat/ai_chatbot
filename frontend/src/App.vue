<!-- Copyright (c) 2026, Sanjay Kumar and contributors -->
<!-- For license information, please see license.txt -->
<template>
  <div class="h-screen bg-white dark:bg-gray-900">
    <router-view />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'

let mediaQuery = null

function applyTheme(isDark) {
  document.documentElement.classList.toggle('dark', isDark)
}

onMounted(() => {
  // Detect OS dark mode preference
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  applyTheme(mediaQuery.matches)
  mediaQuery.addEventListener('change', handleThemeChange)
})

onUnmounted(() => {
  if (mediaQuery) {
    mediaQuery.removeEventListener('change', handleThemeChange)
  }
})

function handleThemeChange(e) {
  applyTheme(e.matches)
}
</script>

<style>
@import 'highlight.js/styles/github-dark.css';

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Custom scrollbar — light */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* Custom scrollbar — dark */
.dark ::-webkit-scrollbar-thumb {
  background: #475569;
}

.dark ::-webkit-scrollbar-thumb:hover {
  background: #64748b;
}

/* Dark mode markdown overrides */
.dark .markdown-body {
  color: #e5e7eb;
}

.dark .markdown-body code {
  background: #374151;
  color: #e5e7eb;
}

.dark .markdown-body a {
  color: #60a5fa;
}

.dark .markdown-body blockquote {
  border-color: #4b5563;
  color: #9ca3af;
}

.dark .markdown-body table th,
.dark .markdown-body table td {
  border-color: #4b5563;
}

.dark .markdown-body table th {
  background: #374151;
}
</style>
