'use client';

interface Player {
  agent_id: string;
  name: string;
  role?: string;
  alive: boolean;
}

interface WerewolfPanelProps {
  players: Player[];
  phase: 'night' | 'day';
  currentTurn: number;
  lastDeath?: string[];
  voteResult?: {
    votes: Record<string, string>;
    vote_counts: Record<string, number>;
    exiled: string;
  };
  gameOver?: { winner: string; roles: Record<string, string> } | null;
}

const ROLE_ICONS: Record<string, string> = {
  werewolf: '🐺',
  seer: '🔮',
  guard: '🛡️',
  villager: '👤',
};

const ROLE_NAMES: Record<string, string> = {
  werewolf: '狼人',
  seer: '预言家',
  guard: '守卫',
  villager: '村民',
};

export default function WerewolfPanel({
  players, phase, currentTurn, lastDeath, voteResult, gameOver,
}: WerewolfPanelProps) {
  return (
    <div className="space-y-4">
      {/* 阶段指示器 */}
      <div className="flex items-center justify-center gap-4 p-3 bg-gray-800 rounded-lg">
        <span className="text-2xl">{phase === 'night' ? '🌙' : '☀️'}</span>
        <span className="text-lg font-semibold text-white">
          {phase === 'night' ? '夜晚' : '白天'} — 第 {currentTurn} 回合
        </span>
      </div>

      {/* 死亡公告 */}
      {lastDeath !== undefined && (
        <div className={`border rounded-lg p-3 text-center ${
          lastDeath.length > 0
            ? 'bg-red-900/30 border-red-700'
            : 'bg-green-900/30 border-green-700'
        }`}>
          <span className={lastDeath.length > 0 ? 'text-red-400' : 'text-green-400'}>
            {lastDeath.length > 0
              ? `💀 昨晚 ${lastDeath.join('、')} 死亡`
              : '✨ 昨晚是平安夜'}
          </span>
        </div>
      )}

      {/* 角色卡牌 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {players.map(player => {
          const revealedRole = gameOver?.roles?.[player.agent_id];
          return (
            <div
              key={player.agent_id}
              className={`relative p-3 rounded-lg border-2 transition-all ${
                player.alive
                  ? 'bg-gray-800 border-gray-600 hover:border-blue-500'
                  : 'bg-gray-900 border-gray-700 opacity-50'
              }`}
            >
              {!player.alive && (
                <div className="absolute inset-0 flex items-center justify-center text-4xl opacity-60 pointer-events-none">
                  💀
                </div>
              )}
              <div className="text-center">
                <div className="text-3xl mb-1">
                  {revealedRole ? ROLE_ICONS[revealedRole] || '❓' : '❓'}
                </div>
                <div className="text-sm font-medium text-white">{player.name}</div>
                {revealedRole && (
                  <div className="text-xs text-gray-400 mt-1">
                    {ROLE_NAMES[revealedRole] || revealedRole}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 投票结果 */}
      {voteResult && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">投票结果</h3>
          <div className="space-y-2">
            {Object.entries(voteResult.vote_counts)
              .sort(([, a], [, b]) => b - a)
              .map(([playerId, count]) => {
                const player = players.find(p => p.agent_id === playerId);
                const total = Object.values(voteResult.vote_counts).reduce((a, b) => a + b, 0);
                const pct = total > 0 ? (count / total) * 100 : 0;
                const isExiled = playerId === voteResult.exiled;
                return (
                  <div key={playerId} className="flex items-center gap-2">
                    <span className={`text-sm w-20 truncate ${isExiled ? 'text-red-400 font-bold' : 'text-gray-300'}`}>
                      {player?.name || playerId.slice(0, 8)}
                    </span>
                    <div className="flex-1 bg-gray-700 rounded-full h-4">
                      <div
                        className={`h-4 rounded-full transition-all ${isExiled ? 'bg-red-500' : 'bg-blue-500'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-400 w-8 text-right">{count}</span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* 游戏结束 */}
      {gameOver && (
        <div className={`text-center p-4 rounded-lg border-2 ${
          gameOver.winner === 'werewolf'
            ? 'bg-red-900/30 border-red-700'
            : 'bg-green-900/30 border-green-700'
        }`}>
          <div className="text-2xl mb-2">
            {gameOver.winner === 'werewolf' ? '🐺' : '🏘️'}
          </div>
          <div className="text-lg font-bold text-white">
            {gameOver.winner === 'werewolf' ? '狼人获胜' : '村民获胜'}
          </div>
        </div>
      )}
    </div>
  );
}