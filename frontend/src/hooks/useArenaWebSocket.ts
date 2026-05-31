import { useEffect, useRef, useState, useCallback } from "react";
import { ArenaMatch, ArenaParticipant } from "@/types";

export interface ArenaEvent {
  type: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

interface UseArenaWebSocketOptions {
  matchId: string | null;
  initialMatch?: ArenaMatch | null;
  initialParticipants?: ArenaParticipant[];
}

export function useArenaWebSocket({ matchId, initialMatch, initialParticipants }: UseArenaWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCount = useRef(0);

  const [connected, setConnected] = useState(false);
  const [match, setMatch] = useState<ArenaMatch | null>(initialMatch || null);
  const [participants, setParticipants] = useState<ArenaParticipant[]>(initialParticipants || []);
  const [events, setEvents] = useState<ArenaEvent[]>([]);
  const [generatingAgent, setGeneratingAgent] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (!matchId) return;

    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const endpoint = `${wsBase}/ws/spectate/arena/${matchId}`;
    const ws = new WebSocket(endpoint);

    ws.onopen = () => {
      setConnected(true);
      retryCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const timestamp = msg.timestamp || new Date().toISOString();
        const data = msg.data || {};

        setEvents((prev) => [...prev, { type: msg.type, timestamp, data }]);

        switch (msg.type) {
          case "match_started":
            setMatch((prev) => prev ? { ...prev, status: "in_progress" } : null);
            setEvents((prev) => [...prev, {
              type: "match_started",
              timestamp,
              data: { message: "对决开始！" }
            }]);
            break;

          case "agent_responded":
            const agentId = data.agent_id as string;
            const agentName = data.agent_name as string;
            const responseContent = data.response_content as ArenaParticipant["response_content"];

            setParticipants((prev) =>
              prev.map((p) =>
                p.agent_id === agentId
                  ? { ...p, response_content: responseContent }
                  : p
              )
            );

            setGeneratingAgent(null);

            setEvents((prev) => [...prev, {
              type: "agent_responded",
              timestamp,
              data: { message: `${agentName} 完成回应` }
            }]);
            break;

          case "voting_started":
            setMatch((prev) => prev ? { ...prev, status: "voting" } : null);
            const votingParticipants = data.participants as ArenaParticipant[] | undefined;
            if (votingParticipants) {
              setParticipants(votingParticipants);
            }
            setEvents((prev) => [...prev, {
              type: "voting_started",
              timestamp,
              data: { message: "投票阶段开始！" }
            }]);
            break;

          case "vote_received":
            const participantId = data.participant_id as string;
            const voteCount = data.vote_count as number;

            setParticipants((prev) =>
              prev.map((p) =>
                p.id === participantId
                  ? { ...p, vote_count: voteCount }
                  : p
              )
            );

            setEvents((prev) => [...prev, {
              type: "vote_received",
              timestamp,
              data: { message: `收到新投票，当前票数: ${voteCount}` }
            }]);
            break;

          case "match_completed":
            const winnerId = data.winner_id as string;
            const winnerName = data.winner_name as string;

            setMatch((prev) => prev ? { ...prev, status: "finished", winner_id: winnerId } : null);

            setEvents((prev) => [...prev, {
              type: "match_completed",
              timestamp,
              data: { message: `对决结束！获胜者: ${winnerName}` }
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
      setGeneratingAgent(null);
      const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
      retryCount.current++;
      reconnectTimeout.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [matchId]);

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
    setEvents([]);
    setGeneratingAgent(null);
    retryCount.current = 0;
  }, []);

  return {
    connected,
    match,
    participants,
    events,
    generatingAgent,
    disconnect,
    setMatch,
    setParticipants,
  };
}
