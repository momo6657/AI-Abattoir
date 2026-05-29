'use client';

import { useEffect, useRef, useCallback, useState } from 'react';

export interface GameEvent {
  type: string;
  turn?: number;
  data?: Record<string, unknown>;
  timestamp?: string;
}

export function useGameWebSocket(gameId: string | null) {
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    if (!gameId) return;

    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const envWsBase = process.env.NEXT_PUBLIC_WS_URL;
    const localHostnames = new Set(['localhost', '127.0.0.1', '::1']);
    const isLocalFrontend = typeof window !== 'undefined' && localHostnames.has(window.location.hostname);
    const wsBase = isLocalFrontend && !envWsBase?.includes('localhost') && !envWsBase?.includes('127.0.0.1')
      ? `${protocol}//${window.location.hostname}:8000`
      : envWsBase || `${protocol}//${window.location.hostname}:8000`;
    const ws = new WebSocket(`${wsBase}/ws/games/${gameId}`);

    ws.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
    };

    ws.onclose = () => {
      setConnected(false);
      const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
      retryCount.current++;
      reconnectTimeout.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setEvents(prev => [...prev, { ...data, timestamp: data.timestamp || new Date().toISOString() }]);
      } catch {
        // ignore non-JSON
      }
    };

    wsRef.current = ws;
  }, [gameId]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, send, clearEvents };
}
