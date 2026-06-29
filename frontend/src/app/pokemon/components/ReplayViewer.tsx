'use client';

import { useEffect, useState, useCallback } from 'react';
import { pokemonApi } from '@/lib/api';

interface ReplayFrame {
  event_index: number;
  event_type: string;
  event_data: Record<string, unknown>;
  description: string;
  side_effects: string[];
}

interface ReplayTurn {
  turn: number;
  summary: string;
  frames: ReplayFrame[];
}

interface ReplayData {
  battle_id: string;
  format: string;
  total_turns: number;
  winner: string | null;
  winner_side?: number | null;
  team1: Record<string, unknown>;
  team2: Record<string, unknown>;
  summary: Record<string, unknown>;
  turns: ReplayTurn[];
}

const EVENT_ICONS: Record<string, string> = {
  move: '⚔️',
  damage: '💥',
  faint: '💀',
  switch: '🔄',
  heal: '💚',
  status: '⚡',
  weather: '🌤️',
  terastallize: '💎',
  turn_start: '▶️',
  turn_end: '⏹️',
};

const EVENT_COLORS: Record<string, string> = {
  move: 'border-sky-400/30 bg-sky-500/5',
  damage: 'border-red-400/30 bg-red-500/5',
  faint: 'border-red-500/40 bg-red-500/10',
  switch: 'border-emerald-400/30 bg-emerald-500/5',
  heal: 'border-green-400/30 bg-green-500/5',
  status: 'border-amber-400/30 bg-amber-500/5',
  terastallize: 'border-violet-400/30 bg-violet-500/5',
};

function FrameCard({ frame }: { frame: ReplayFrame }) {
  const icon = EVENT_ICONS[frame.event_type] || '📝';
  const color = EVENT_COLORS[frame.event_type] || 'border-border bg-black/20';

  return (
    <div className={`rounded-lg border p-3 ${color} transition`}>
      <div className="flex items-start gap-2">
        <span className="shrink-0 text-base">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-gray-200">{frame.description}</p>
          {frame.side_effects.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {frame.side_effects.map((effect, i) => (
                <span key={i} className="rounded bg-black/20 px-1.5 py-0.5 text-[10px] text-gray-500">
                  {effect}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className="shrink-0 text-[10px] text-gray-600">#{frame.event_index}</span>
      </div>
    </div>
  );
}

export default function ReplayViewer({ battleId }: { battleId?: string }) {
  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentTurn, setCurrentTurn] = useState(0);
  const [autoPlay, setAutoPlay] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1000);

  useEffect(() => {
    if (battleId) loadReplay(battleId);
  }, [battleId]);

  useEffect(() => {
    if (!autoPlay || !replay) return;
    const timer = setInterval(() => {
      setCurrentTurn((prev) => {
        if (prev >= (replay?.turns.length || 1) - 1) {
          setAutoPlay(false);
          return prev;
        }
        return prev + 1;
      });
    }, playSpeed);
    return () => clearInterval(timer);
  }, [autoPlay, playSpeed, replay]);

  const loadReplay = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await pokemonApi.getBattleReplay(id);
      setReplay(res.data);
      setCurrentTurn(0);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '加载回放失败');
    } finally {
      setLoading(false);
    }
  }, []);

  if (!battleId) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm text-gray-500">选择一场对战以查看回放。</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card p-8 text-center">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        <p className="mt-3 text-sm text-gray-400">加载回放...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6">
        <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      </div>
    );
  }

  if (!replay) return null;

  if (replay.turns.length === 0) {
    return (
      <div className="card p-8 text-center">
        <h2 className="text-base font-semibold text-white">对战回放</h2>
        <p className="mt-2 text-sm text-gray-500">这场对战还没有可回放的事件。</p>
      </div>
    );
  }

  const turn = replay.turns[currentTurn];

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="border-b border-border bg-surface-raised/50 px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">🎮 对战回放</h2>
            <p className="mt-1 text-xs text-gray-500">
              {replay.format} · {replay.total_turns} 回合
              {replay.winner && ` · 胜者: ${replay.winner}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={playSpeed}
              onChange={(e) => setPlaySpeed(Number(e.target.value))}
              className="rounded border border-border bg-black/30 px-2 py-1 text-xs text-gray-300"
            >
              <option value={2000}>0.5x</option>
              <option value={1000}>1x</option>
              <option value={500}>2x</option>
              <option value={250}>4x</option>
            </select>
          </div>
        </div>
      </div>

      {/* Turn Navigation */}
      <div className="border-b border-border bg-black/20 px-5 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setCurrentTurn(0)}
            disabled={currentTurn === 0}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-30"
          >
            ⏮
          </button>
          <button
            onClick={() => setCurrentTurn((p) => Math.max(0, p - 1))}
            disabled={currentTurn === 0}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-30"
          >
            ◀
          </button>
          <button
            onClick={() => setAutoPlay(!autoPlay)}
            className={`px-3 py-1 text-xs rounded ${autoPlay ? 'bg-red-500/20 text-red-300' : 'bg-accent/20 text-accent'}`}
          >
            {autoPlay ? '⏸ 暂停' : '▶ 播放'}
          </button>
          <button
            onClick={() => setCurrentTurn((p) => Math.min((replay?.turns.length || 1) - 1, p + 1))}
            disabled={currentTurn >= replay.turns.length - 1}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-30"
          >
            ▶
          </button>
          <button
            onClick={() => setCurrentTurn(replay.turns.length - 1)}
            disabled={currentTurn >= replay.turns.length - 1}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-30"
          >
            ⏭
          </button>

          {/* Progress bar */}
          <div className="flex-1">
            <input
              type="range"
              min={0}
              max={replay.turns.length - 1}
              value={currentTurn}
              onChange={(e) => setCurrentTurn(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>
          <span className="text-xs text-gray-400">
            {currentTurn + 1}/{replay.turns.length}
          </span>
        </div>
      </div>

      {/* Turn Content */}
      <div className="p-5">
        {turn && (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-white">回合 {turn.turn}</h3>
              <span className="text-xs text-gray-500">{turn.frames.length} 个事件</span>
            </div>
            <div className="space-y-2">
              {turn.frames.map((frame) => (
                <FrameCard key={frame.event_index} frame={frame} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Turn List */}
      <div className="border-t border-border bg-black/10 px-5 py-3">
        <div className="flex flex-wrap gap-1">
          {replay.turns.map((t, i) => (
            <button
              key={t.turn}
              onClick={() => setCurrentTurn(i)}
              className={`h-7 w-7 rounded text-xs font-medium transition ${
                i === currentTurn
                  ? 'bg-accent text-white'
                  : i < currentTurn
                    ? 'bg-surface-overlay text-gray-400 hover:text-white'
                    : 'bg-black/20 text-gray-600 hover:text-gray-400'
              }`}
            >
              {t.turn}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
