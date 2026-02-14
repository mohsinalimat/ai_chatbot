/**
 * Shared marked (markdown) configuration.
 *
 * Import `renderMarkdown` wherever you need to convert markdown → HTML.
 * All links are opened in a new tab with rel="noopener noreferrer".
 */
import { marked } from 'marked'
import hljs from 'highlight.js'

marked.use({
  breaks: true,
  gfm: true,
})

/**
 * Render a markdown string to HTML.
 *
 * Post-processes the output to:
 * - Open all links in a new tab (target="_blank")
 * - Apply syntax highlighting to code blocks via highlight.js
 *
 * @param {string} content - Markdown text
 * @returns {string} HTML string
 */
export function renderMarkdown(content) {
  let html = marked(content)

  // Open all links in a new tab
  html = html.replace(
    /<a href="/g,
    '<a target="_blank" rel="noopener noreferrer" href="'
  )

  // Syntax highlighting for code blocks: <code class="language-xyz">
  html = html.replace(
    /<code class="language-(\w+)">([\s\S]*?)<\/code>/g,
    (_match, lang, code) => {
      const decoded = code.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
      if (hljs.getLanguage(lang)) {
        const highlighted = hljs.highlight(decoded, { language: lang }).value
        return `<code class="hljs language-${lang}">${highlighted}</code>`
      }
      return `<code class="hljs">${hljs.highlightAuto(decoded).value}</code>`
    }
  )

  return html
}
