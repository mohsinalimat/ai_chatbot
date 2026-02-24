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
let themeObserver = null

function applyTheme(isDark) {
  document.documentElement.classList.toggle('dark', isDark)
}

function detectTheme() {
  // Frappe's data-theme attribute takes priority (injected server-side from user's desk_theme)
  const themeMode = document.documentElement.getAttribute('data-theme-mode')
  const dataTheme = document.documentElement.getAttribute('data-theme')

  // "automatic" mode defers to OS preference
  if (themeMode === 'automatic' || dataTheme === 'automatic') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  // Explicit theme set
  if (dataTheme) {
    return dataTheme === 'dark'
  }

  // Fallback to OS preference
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

async function fetchAndApplyTheme() {
  // Fetch current desk_theme from Frappe API (handles theme changes in other tabs)
  try {
    const response = await fetch('/api/method/frappe.client.get_value', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': window.csrf_token || '',
      },
      credentials: 'include',
      body: JSON.stringify({
        doctype: 'User',
        filters: { name: decodeURIComponent(document.cookie.match(/user_id=([^;]+)/)?.[1] || '') },
        fieldname: 'desk_theme',
      }),
    })
    if (response.ok) {
      const data = await response.json()
      const theme = (data.message?.desk_theme || 'Light').toLowerCase()
      document.documentElement.setAttribute('data-theme-mode', theme)
      // Resolve automatic → actual theme
      if (theme === 'automatic') {
        const resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
        document.documentElement.setAttribute('data-theme', resolved)
      } else {
        document.documentElement.setAttribute('data-theme', theme)
      }
      applyTheme(detectTheme())
    }
  } catch {
    // Silently fall back to current attributes
  }
}

onMounted(() => {
  // Apply initial theme from server-injected data-theme attribute
  applyTheme(detectTheme())

  // Watch for data-theme attribute changes (in case anything modifies it at runtime)
  themeObserver = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes' && (mutation.attributeName === 'data-theme' || mutation.attributeName === 'data-theme-mode')) {
        applyTheme(detectTheme())
      }
    }
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-theme-mode'],
  })

  // Watch OS preference (for automatic mode)
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', handleOSThemeChange)

  // Re-sync theme when user returns to this tab (catches theme changes in Frappe desk)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  if (themeObserver) {
    themeObserver.disconnect()
  }
  if (mediaQuery) {
    mediaQuery.removeEventListener('change', handleOSThemeChange)
  }
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

function handleOSThemeChange() {
  applyTheme(detectTheme())
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible') {
    fetchAndApplyTheme()
  }
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

/* Markdown base styles (light mode) */
.markdown-body {
  color: #1f2937;
}

.markdown-body p {
  margin-bottom: 0.75rem;
}

.markdown-body code {
  background: #f3f4f6;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.markdown-body pre {
  background: #111827;
  color: #f3f4f6;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 1rem 0;
}

.markdown-body pre code {
  background: transparent;
  padding: 0;
  font-size: 0.875rem;
}

.markdown-body a {
  color: #2563eb;
  text-decoration: underline;
}

.markdown-body a:hover {
  color: #1e40af;
}

.markdown-body blockquote {
  border-left: 4px solid #d1d5db;
  padding-left: 1rem;
  font-style: italic;
  color: #4b5563;
  margin: 0.75rem 0;
}

.markdown-body ul,
.markdown-body ol {
  margin-left: 1.5rem;
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
}

.markdown-body li {
  margin-bottom: 0.25rem;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}

.markdown-body h1 { font-size: 1.5rem; }
.markdown-body h2 { font-size: 1.25rem; }
.markdown-body h3 { font-size: 1.125rem; }

.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
}

.markdown-body table th,
.markdown-body table td {
  border: 1px solid #d1d5db;
  padding: 0.5rem 1rem;
}

.markdown-body table th {
  background: #f9fafb;
  font-weight: 600;
  text-align: left;
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

.dark .markdown-body a:hover {
  color: #93c5fd;
}

.dark .markdown-body blockquote {
  border-color: #4b5563;
  color: #9ca3af;
}

.dark .markdown-body table th,
.dark .markdown-body table td {
  border-color: #4b5563;
  color: #e5e7eb;
}

.dark .markdown-body table td {
  background: #1f2937;
}

.dark .markdown-body table th {
  background: #374151;
  color: #f3f4f6;
}
</style>
