import { useEffect, useRef, useState, useCallback } from 'react'

interface UseWebSocketOptions {
  onMessage?: (data: any) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
}

export const useWebSocket = (url: string | null, options: UseWebSocketOptions = {}) => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null)
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const maxReconnect = 5
  // 使用 ref 存储回调函数，避免依赖变化导致重连
  const optionsRef = useRef(options)
  optionsRef.current = options

  useEffect(() => {
    if (!url) {
      setReadyState(WebSocket.CLOSED)
      return
    }

    const connect = () => {
      console.log(`[WebSocket] Connecting to ${url}, reconnectCount: ${reconnectCountRef.current}`)
      const ws = new WebSocket(url)
      wsRef.current = ws
      setReadyState(WebSocket.CONNECTING)

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        reconnectCountRef.current = 0
        setReadyState(WebSocket.OPEN)
        optionsRef.current.onConnect?.()
      }

      ws.onmessage = (event) => {
        console.log('[WebSocket] Received message:', event.data?.substring(0, 200))
        setLastMessage(event)
        try {
          const data = JSON.parse(event.data)
          optionsRef.current.onMessage?.(data)
        } catch {
          optionsRef.current.onMessage?.(event.data)
        }
      }

      ws.onclose = (event) => {
        console.log(`[WebSocket] Closed: code=${event.code}, reason=${event.reason}`)
        setReadyState(WebSocket.CLOSED)
        optionsRef.current.onDisconnect?.()
        
        // 自动重连
        if (reconnectCountRef.current < maxReconnect) {
          reconnectCountRef.current++
          console.log(`[WebSocket] Reconnecting in 3s... (${reconnectCountRef.current}/${maxReconnect})`)
          setTimeout(connect, 3000)
        }
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
        // 只在连接未打开时打印错误，避免正常关闭时的误报
        if (ws.readyState !== WebSocket.OPEN) {
          console.warn('WebSocket connection error:', error)
        }
        setReadyState(WebSocket.CLOSED)
        optionsRef.current.onError?.(error)
      }
    }

    connect()

    return () => {
      console.log('[WebSocket] Cleanup - closing connection')
      wsRef.current?.close()
    }
  }, [url]) // 只依赖 url，避免频繁重连

  const sendMessage = useCallback((data: string | object) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      wsRef.current.send(message)
    }
  }, [])

  const close = useCallback(() => {
    wsRef.current?.close()
  }, [])

  return { lastMessage, readyState, sendMessage, close }
}

export default useWebSocket
