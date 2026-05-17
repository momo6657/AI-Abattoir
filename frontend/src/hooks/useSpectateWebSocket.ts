import { useEffect, useRef, useState, useCallback } from "react";

export interface SpectateMessage {
  id: string;
  agent_id?: string;
  agent_name?: string;
  role?: string;
  content: string;
  turn_number?: number;
  log_type?: string;
  created_at: string;
}

interface UseSpectateWebSocketOptions {
  targetId: string | null;
  type: "conversation" | "game";
}

export function useSpectateWebSocket({ targetId, type }: UseSpectateWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<SpectateMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const [thinkingAgent, setThinkingAgent] = useState<string | null>(null);
  const [gameEvents, setGameEvents] = useState<Record<string, unknown>[]>([]);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  const connect = useCallback(() => {
    if (!targetId) return;

    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const endpoint = type === "conversation"
      ? `${wsBase}/ws/spectate/conversation/${targetId}`
      : `${wsBase}/ws/spectate/game/${targetId}`;
    const ws = new WebSocket(endpoint);

    ws.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const payload = msg.data || {};
        switch (msg.type) {
          case "new_message":
            setMessages((prev) => [...prev, {
              id: payload.id || crypto.randomUUID(),
              agent_id: payload.agent_id,
              agent_name: payload.agent_name,
              role: payload.role || "agent",
              content: typeof payload.content === "string" ? payload.content : JSON.stringify(payload.content),
              turn_number: payload.turn_number,
              created_at: payload.created_at || new Date().toISOString(),
            }]);
            break;
          case "agent_thinking":
            setThinkingAgent(payload.agent_name || payload.agent_id || null);
            break;
          case "agent_done_thinking":
            setThinkingAgent(null);
            break;
          case "game_event":
          case "turn_start":
          case "turn_end":
          case "phase_change":
          case "vote_result":
          case "elimination":
            setGameEvents((prev) => [...prev, { type: msg.type, ...payload, timestamp: new Date().toISOString() }]);
            if (msg.type === "elimination") {
              setMessages((prev) => [...prev, {
                id: crypto.randomUUID(),
                role: "system",
                content: payload.content || `${payload.agent_name || "玩家"} 已被淘汰`,
                log_type: "elimination",
                created_at: new Date().toISOString(),
              }]);
            }
            break;
          case "game_started":
          case "game_ended":
            setGameEvents((prev) => [...prev, { type: msg.type, ...payload, timestamp: new Date().toISOString() }]);
            setMessages((prev) => [...prev, {
              id: crypto.randomUUID(),
              role: "system",
              content: msg.type === "game_started" ? "游戏开始" : "游戏结束",
              log_type: "system",
              created_at: new Date().toISOString(),
            }]);
            break;
          case "conversation_started":
          case "conversation_ended":
          case "conversation_paused":
            setMessages((prev) => [...prev, {
              id: crypto.randomUUID(),
              role: "system",
              content: msg.type === "conversation_started" ? "对话开始"
                : msg.type === "conversation_ended" ? "对话结束" : "对话已暂停",
              log_type: "system",
              created_at: new Date().toISOString(),
            }]);
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
      const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
      retryCount.current++;
      reconnectTimeout.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [targetId, type]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    if (wsRef.current) wsRef.current.close();
    wsRef.current = null;
    setConnected(false);
    setMessages([]);
    setThinkingAgent(null);
    setGameEvents([]);
    retryCount.current = 0;
  }, []);

  return { messages, connected, thinkingAgent, gameEvents, disconnect, setMessages };
}
