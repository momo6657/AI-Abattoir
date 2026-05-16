import { useEffect, useRef, useState, useCallback } from "react";

interface WSEvent {
  type: string;
  data?: Record<string, unknown>;
}

export function useWebSocket(conversationId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<Record<string, unknown>[]>([]);
  const [thinkingAgent, setThinkingAgent] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [conversationEnded, setConversationEnded] = useState(false);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    if (!conversationId) return;

    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const ws = new WebSocket(`${wsBase}/ws/conversations/${conversationId}`);

    ws.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSEvent;
        const payload = msg.data || {};
        switch (msg.type) {
          case "new_message":
            setMessages((prev) => [...prev, payload]);
            break;
          case "agent_thinking":
            setThinkingAgent(payload.agent_id as string);
            break;
          case "agent_done_thinking":
            setThinkingAgent(null);
            break;
          case "conversation_started":
            setConversationEnded(false);
            break;
          case "conversation_ended":
            setConversationEnded(true);
            setThinkingAgent(null);
            break;
          case "conversation_paused":
            setThinkingAgent(null);
            break;
          case "ping":
            ws.send(JSON.stringify({ type: "pong" }));
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setThinkingAgent(null);
      // Reconnect with exponential backoff
      const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
      retryCount.current++;
      reconnectTimeout.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [conversationId]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { messages, setMessages, thinkingAgent, connected, conversationEnded, send };
}
