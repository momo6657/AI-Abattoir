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

const GAME_EVENT_TYPES = new Set([
  "game_start",
  "night_result",
  "day_discussion",
  "vote_result",
  "game_over",
  "max_turns_reached",
  "turn_error",
  "turn_timeout",
  "error",
]);

function getGameEventData(message: Record<string, unknown>): Record<string, unknown> {
  const payload = (message.data || {}) as Record<string, unknown>;
  const nested = payload.data;
  return nested && typeof nested === "object" ? nested as Record<string, unknown> : payload;
}

function formatGameEventContent(type: string, data: Record<string, unknown>): string {
  if (typeof data.message === "string" && data.message.trim()) return data.message;
  if (type === "game_start") return `游戏开始：${data.player_count || 0} 名玩家入场`;
  if (type === "night_result") {
    const names = Array.isArray(data.death_names) ? data.death_names : data.deaths;
    return Array.isArray(names) && names.length > 0 ? `昨晚 ${names.join("、")} 死亡` : "昨晚是平安夜";
  }
  if (type === "day_discussion") return "白天讨论完成";
  if (type === "vote_result") return `投票结果：${data.exiled_name || data.exiled || "玩家"} 被放逐`;
  if (type === "game_over") return data.winner === "werewolf" ? "游戏结束：狼人阵营获胜" : "游戏结束：村民阵营获胜";
  if (type === "max_turns_reached") return "游戏达到最大回合数";
  return String(data.message || type);
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
        if (type === "game" && GAME_EVENT_TYPES.has(msg.type)) {
          const eventData = getGameEventData(msg);
          setGameEvents((prev) => [...prev, { type: msg.type, ...eventData, timestamp: msg.timestamp || new Date().toISOString() }]);

          if (msg.type === "day_discussion" && Array.isArray(eventData.speeches)) {
            setMessages((prev) => [
              ...prev,
              ...(eventData.speeches as { agent_id?: string; name?: string; content?: string; role?: string }[]).map((speech) => ({
                id: crypto.randomUUID(),
                agent_id: speech.agent_id,
                agent_name: speech.name || "玩家",
                role: speech.role || "agent",
                content: speech.content || "",
                turn_number: Number(payload.turn || eventData.turn || 0) || undefined,
                log_type: "speech",
                created_at: msg.timestamp || new Date().toISOString(),
              })),
            ]);
          } else {
            setMessages((prev) => [...prev, {
              id: crypto.randomUUID(),
              role: "system",
              content: formatGameEventContent(msg.type, eventData),
              turn_number: Number(payload.turn || eventData.turn || 0) || undefined,
              log_type: msg.type === "night_result" || msg.type === "vote_result" ? "elimination" : "system",
              created_at: msg.timestamp || new Date().toISOString(),
            }]);
          }
          return;
        }
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
