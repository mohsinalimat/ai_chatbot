/**
 * Socket.IO Client Composable
 *
 * Manages connection to Frappe's Socket.IO server from a standalone Vue app
 * (outside Frappe desk). Follows the same pattern as Frappe CRM.
 *
 * Connection details:
 * - socketio_port: imported from common_site_config.json
 * - site_name: injected into window by the server-rendered HTML template
 * - Auth: via session cookie (sid) with withCredentials: true
 */

import { ref } from 'vue'
import { Manager } from 'socket.io-client'
import { socketio_port } from '../../../../../sites/common_site_config.json'

let socket = null
const isConnected = ref(false)
const connectionError = ref(null)

/**
 * Initialize the Socket.IO connection (singleton).
 * Connects to Frappe's Socket.IO server using the site namespace.
 *
 * We use Manager + socket(namespace) instead of io(url/namespace) to avoid
 * a URL parsing bug in socket.io-client where the namespace path (e.g.
 * "/test.local") collides with the hostname ("test.local"), corrupting
 * the connection URL.
 */
function initSocket() {
  if (socket && socket.connected) {
    return socket
  }

  try {
    const host = window.location.hostname
    const siteName = window.site_name || window.location.hostname
    const port = window.location.port ? `:${socketio_port}` : ''
    const protocol = window.location.protocol
    const baseUrl = `${protocol}//${host}${port}`

    console.debug(`[AI Chatbot] Socket.IO connecting to: ${baseUrl} (namespace: /${siteName})`)

    // Create a Manager for the base URL (no namespace in the URL)
    const manager = new Manager(baseUrl, {
      withCredentials: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      timeout: 10000,
    })

    // Connect to the site-specific namespace separately
    socket = manager.socket(`/${siteName}`)

    socket.on('connect', () => {
      isConnected.value = true
      connectionError.value = null
      console.debug('[AI Chatbot] Socket.IO connected')
    })

    socket.on('disconnect', (reason) => {
      isConnected.value = false
      console.debug('[AI Chatbot] Socket.IO disconnected:', reason)
    })

    socket.on('connect_error', (error) => {
      isConnected.value = false
      connectionError.value = error.message
      console.warn('[AI Chatbot] Socket.IO connection error:', error.message)
    })

    return socket
  } catch (error) {
    connectionError.value = error.message
    console.error('[AI Chatbot] Failed to init Socket.IO:', error)
    return null
  }
}

/**
 * Get the current socket instance, initializing if needed.
 */
function getSocket() {
  if (!socket || !socket.connected) {
    initSocket()
  }
  return socket
}

/**
 * Subscribe to a realtime event.
 * @param {string} event - Event name (e.g., 'ai_chat_token')
 * @param {Function} callback - Event handler
 */
function on(event, callback) {
  if (socket) {
    socket.on(event, callback)
  }
}

/**
 * Unsubscribe from a realtime event.
 * @param {string} event - Event name
 * @param {Function} [callback] - Specific handler to remove (removes all if omitted)
 */
function off(event, callback) {
  if (socket) {
    if (callback) {
      socket.off(event, callback)
    } else {
      socket.off(event)
    }
  }
}

/**
 * Disconnect the socket.
 */
function disconnect() {
  if (socket) {
    socket.disconnect()
    socket = null
    isConnected.value = false
  }
}

/**
 * Vue composable for Socket.IO connection.
 */
export function useSocket() {
  return {
    isConnected,
    connectionError,
    initSocket,
    getSocket,
    on,
    off,
    disconnect,
  }
}
