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
  const { onMessage, onConnect, onDisconnect, onError } = options

  useEffect(() => {
    if (!url) return

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setReadyState(WebSocket.OPEN)
      onConnect?.()
    }

    ws.onmessage = (event) => {
      setLastMessage(event)
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        onMessage?.(event.data)
      }
    }

    ws.onclose = () => {
      setReadyState(WebSocket.CLOSED)
      onDisconnect?.()
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setReadyState(WebSocket.CLOSED)
      onError?.(error)
    }

    return () => {
      ws.close()
    }
  }, [url, onMessage, onConnect, onDisconnect, onError])

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
