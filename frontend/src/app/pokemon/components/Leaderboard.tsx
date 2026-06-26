'use client';

import { useEffect, useState } from 'react';
import { pokemonApi } from '@/lib/api';

interface LeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  rating: number;
  tier: string;
  tier_zh: string;
  battles: number;
  wins: number;
  losses: number;
  win_rate: number;
  peak_rating: number;
  current_streak: number;
  best_streak: number;
  favorite_format: string | null;
  playstyle: string | null;
  level: string;
}

const TIER_COLORS: Record<string, string> = {
  Grandmaster: 'from-yellow-400 to-amber-500 text-amber-900',
  Master: 'from-violet-400 to-purple-500 text-purple-900',
  Diamond: 'from-sky-400 to-cyan-500 text-cyan-900',
  Platinum: 'from-emerald-400 to-teal-500 text-teal-900',
  Gold: 'from-yellow-300 to-amber-400 text-amber-900',
  Silver: 'from-gray-300 to-gray-400 text-gray-900',
  Bronze: 'from-orange-400 to-amber-600 text-amber-900',
};

const TIER_ICONS: Record<string, string> = {
  Grandmaster: '👑',
  Master: '💎',
  Diamond: '💠',
  Platinum: '🏅',
  Gold: '🥇',
  Silver: '🥈',
  Bronze: '🥉',
};

function TierBadge({ tier, tierZh }: { tier: string; tierZh: string }) {
  const colors = TIER_COLORS[tier] || TIER_COLORS.Bronze;
  const icon = TIER_ICONS[tier] || '⚔️';
  return (
    <span className={`inline-flex items-center gap-1 rounded-full bg-gradient-to-r ${colors} px-2.5 py-0.5 text-xs font-semibold`}>
      {icon} {tierZh}
    </span>
  );
}

function StreakIndicator({ streak }: { streak: number }) {
  if (streak === 0) return null;
  const isWin = streak > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs ${isWin ? 'text-emerald-400' : 'text-red-400'}`}>
      {isWin ? '🔥' : '❄️'} {Math.abs(streak)}
    </span>
  );
}

export default function Leaderboard({ format }: { format?: string }) {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLeaderboard();
  }, [format]);

  async function loadLeaderboard() {
    setLoading(true);
    setError(null);
    try {
      const res = await pokemonApi.listPokemonLeaderboard(format, 20);
      setEntries(res.data || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '加载排行榜失败');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-center gap-3 py-8">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <span className="text-sm text-gray-400">加载排行榜...</span>
        </div>
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

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-border bg-surface-raised/50 px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">🏆 宝可梦排行榜</h2>
            <p className="mt-1 text-xs text-gray-500">Elo 评分排名 · {format || '全部格式'}</p>
          </div>
          <button
            onClick={loadLeaderboard}
            className="btn-ghost text-xs"
          >
            刷新
          </button>
        </div>
      </div>

      {entries.length === 0 ? (
        <div className="p-8 text-center text-sm text-gray-500">
          暂无排名数据，完成对战后自动更新。
        </div>
      ) : (
        <div className="divide-y divide-border">
          {entries.map((entry, index) => (
            <div
              key={entry.agent_id}
              className={`flex items-center gap-4 px-5 py-3 transition hover:bg-surface-overlay/30 ${
                index < 3 ? 'bg-surface-overlay/10' : ''
              }`}
            >
              {/* Rank */}
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
                index === 0 ? 'bg-yellow-500/20 text-yellow-300' :
                index === 1 ? 'bg-gray-400/20 text-gray-300' :
                index === 2 ? 'bg-orange-500/20 text-orange-300' :
                'bg-surface-overlay text-gray-500'
              }`}>
                {entry.rank}
              </div>

              {/* Name & Tier */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium text-white">{entry.agent_name}</span>
                  <TierBadge tier={entry.tier} tierZh={entry.tier_zh} />
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                  <span>{entry.level}</span>
                  {entry.playstyle && <span>· {entry.playstyle}</span>}
                  {entry.favorite_format && <span>· {entry.favorite_format}</span>}
                </div>
              </div>

              {/* Rating */}
              <div className="text-right">
                <div className="text-lg font-bold text-white">{entry.rating}</div>
                <div className="text-[10px] text-gray-500">
                  峰值 {entry.peak_rating}
                </div>
              </div>

              {/* Stats */}
              <div className="hidden text-right sm:block">
                <div className="text-sm text-gray-300">
                  {entry.wins}胜 {entry.losses}负
                </div>
                <div className="flex items-center justify-end gap-2 text-xs text-gray-500">
                  <span>{entry.win_rate}%</span>
                  <StreakIndicator streak={entry.current_streak} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
