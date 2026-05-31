'use client';

interface PlayerSnapshot {
  agent_id: string;
  name: string;
  role?: string;
  role_name?: string;
  alive?: boolean;
}

interface WerewolfGameStateProps {
  phase?: 'night' | 'day' | 'vote' | 'result';
  turn?: number;
  players?: PlayerSnapshot[];
  nightActions?: {
    kill_target?: { name?: string } | null;
    guard_target?: { name?: string } | null;
    seer_check?: { target_name?: string; is_werewolf?: boolean } | null;
    witch_save?: boolean;
    witch_poison_target?: { name?: string } | null;
  };
  deathNames?: string[];
  exiledName?: string;
  winner?: string | null;
  aliveCount?: number;
}

const PHASE_LABELS: Record<string, string> = {
  night: '🌙 夜晚',
  day: '☀️ 白天讨论',
  vote: '🗳️ 投票放逐',
  result: '🏆 游戏结束',
};

const ROLE_ICONS: Record<string, string> = {
  werewolf: '🐺',
  seer: '🔮',
  guard: '🛡️',
  witch: '🧪',
  hunter: '🔫',
  villager: '👤',
};

export default function WerewolfGameState({
  phase,
  turn,
  players = [],
  nightActions,
  deathNames = [],
  exiledName,
  winner,
  aliveCount,
}: WerewolfGameStateProps) {
  return (
    <div className="space-y-3">
      {/* Phase & Turn */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">
          {phase ? PHASE_LABELS[phase] || phase : '狼人杀'}
        </span>
        <div className="flex items-center gap-2">
          {turn != null && (
            <span className="text-xs text-gray-400">回合 {turn}</span>
          )}
          {aliveCount != null && (
            <span className="text-xs text-green-400">存活 {aliveCount} 人</span>
          )}
        </div>
      </div>

      {/* Player Grid */}
      {players.length > 0 && (
        <div className="grid grid-cols-2 gap-1.5">
          {players.map((p) => (
            <div
              key={p.agent_id}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${
                p.alive !== false
                  ? 'bg-gray-700 text-gray-200'
                  : 'bg-gray-800/50 text-gray-500 line-through'
              }`}
            >
              <span>{ROLE_ICONS[p.role || ''] || '❓'}</span>
              <span className="truncate">{p.name}</span>
              {p.role_name && (
                <span className="text-gray-500 ml-auto text-[10px]">{p.role_name}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Night Actions */}
      {phase === 'night' && nightActions && (
        <div className="bg-indigo-900/30 rounded p-2 space-y-1 text-xs">
          {nightActions.kill_target?.name && (
            <div>🐺 狼人袭击: <span className="text-red-400">{nightActions.kill_target.name}</span></div>
          )}
          {nightActions.guard_target?.name && (
            <div>🛡️ 守卫守护: <span className="text-blue-400">{nightActions.guard_target.name}</span></div>
          )}
          {nightActions.seer_check && (
            <div>
              🔮 预言家查验: {nightActions.seer_check.target_name}
              {nightActions.seer_check.is_werewolf ? (
                <span className='text-red-400 ml-1'>狼人!</span>
              ) : (
                <span className="text-green-400 ml-1">好人</span>
              )}
            </div>
          )}
          {nightActions.witch_save && <div>🧪 女巫使用了解药</div>}
          {nightActions.witch_poison_target?.name && (
            <div>🧪 女巫毒杀: <span className="text-red-400">{nightActions.witch_poison_target.name}</span></div>
          )}
        </div>
      )}

      {/* Deaths */}
      {deathNames.length > 0 && (
        <div className="bg-red-900/20 rounded p-2 text-xs">
          💀 死亡: <span className="text-red-400">{deathNames.join('、')}</span>
        </div>
      )}

      {/* Exile */}
      {exiledName && (
        <div className="bg-yellow-900/20 rounded p-2 text-xs">
          🗳️ 放逐: <span className="text-yellow-400">{exiledName}</span>
        </div>
      )}

      {/* Winner */}
      {winner && (
        <div className="bg-green-900/30 rounded p-2 text-center text-sm font-bold">
          🏆 {winner === 'werewolf' ? '狼人阵营获胜' : winner === 'village' ? '村民阵营获胜' : winner}
        </div>
      )}
    </div>
  );
}
