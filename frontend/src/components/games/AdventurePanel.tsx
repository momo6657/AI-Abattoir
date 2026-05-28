'use client';

interface AdventureState {
  hp: number;
  max_hp: number;
  inventory: string[];
  current_location: string;
  explored_locations: string[];
}

interface AdventurePanelProps {
  scene?: string;
  options?: Record<string, string>;
  lastResult?: {
    choice: string;
    result: string;
    hp_change?: number;
    item?: string;
    new_location?: string;
  };
  state: AdventureState;
  gameOver?: { result: string } | null;
  onChoice?: (optionKey: string) => void;
}

export default function AdventurePanel({
  scene, options, lastResult, state, gameOver, onChoice,
}: AdventurePanelProps) {
  const hpPercent = state.max_hp > 0 ? (state.hp / state.max_hp) * 100 : 0;
  const hpColor = hpPercent > 60 ? 'bg-green-500' : hpPercent > 30 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="space-y-4">
      {/* 状态栏 */}
      <div className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg">
        <div className="flex items-center gap-2 flex-1">
          <span className="text-sm text-gray-300">❤️ HP</span>
          <div className="flex-1 bg-gray-700 rounded-full h-3">
            <div className={`${hpColor} rounded-full h-3 transition-all duration-500`} style={{ width: `${hpPercent}%` }} />
          </div>
          <span className="text-sm text-gray-300">{state.hp}/{state.max_hp}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-sm">📍</span>
          <span className="text-sm text-gray-300">{state.current_location}</span>
        </div>
      </div>

      {/* 物品栏 */}
      {state.inventory.length > 0 && (
        <div className="flex items-center gap-2 p-2 bg-gray-800/50 rounded-lg flex-wrap">
          <span className="text-sm text-gray-400">🎒</span>
          {state.inventory.map((item, i) => (
            <span key={i} className="px-2 py-0.5 bg-gray-700 text-sm text-gray-200 rounded">{item}</span>
          ))}
        </div>
      )}

      {/* 场景描述 */}
      {scene && (
        <div className="p-4 bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg border border-gray-700">
          <p className="text-gray-200 leading-relaxed">{scene}</p>
        </div>
      )}

      {/* 上次行动结果 */}
      {lastResult && (
        <div className={`p-3 rounded-lg border ${
          lastResult.hp_change && lastResult.hp_change < 0
            ? 'bg-red-900/20 border-red-800'
            : lastResult.hp_change && lastResult.hp_change > 0
              ? 'bg-green-900/20 border-green-800'
              : 'bg-gray-800 border-gray-700'
        }`}>
          <p className="text-sm text-gray-200">{lastResult.result}</p>
          <div className="flex gap-3 mt-2">
            {lastResult.hp_change && (
              <span className={lastResult.hp_change > 0 ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
                HP {lastResult.hp_change > 0 ? '+' : ''}{lastResult.hp_change}
              </span>
            )}
            {lastResult.item && lastResult.item !== 'NONE' && (
              <span className="text-yellow-400 text-sm">获得：{lastResult.item}</span>
            )}
            {lastResult.new_location && (
              <span className="text-blue-400 text-sm">移动到：{lastResult.new_location}</span>
            )}
          </div>
        </div>
      )}

      {/* 行动选项 */}
      {options && Object.keys(options).length > 0 && !gameOver && onChoice && (
        <div className="space-y-2">
          {Object.entries(options).map(([key, desc]) => (
            <button
              key={key}
              onClick={() => onChoice(key)}
              className="w-full text-left p-3 bg-gray-800 hover:bg-gray-700 border border-gray-600 hover:border-blue-500 rounded-lg transition-colors"
            >
              <span className="text-blue-400 font-medium mr-2">{key.replace('OPTION_', '')}</span>
              <span className="text-gray-200 text-sm">{desc}</span>
            </button>
          ))}
        </div>
      )}

      {/* 已探索区域 */}
      {state.explored_locations.length > 1 && (
        <div className="p-3 bg-gray-800/50 rounded-lg">
          <span className="text-xs text-gray-400">已探索区域</span>
          <div className="flex gap-2 mt-1 flex-wrap">
            {state.explored_locations.map(loc => (
              <span key={loc} className={`px-2 py-0.5 text-xs rounded ${
                loc === state.current_location
                  ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
                  : 'bg-gray-700 text-gray-400'
              }`}>
                {loc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 游戏结束 */}
      {gameOver && (
        <div className="text-center p-6 bg-red-900/30 border border-red-700 rounded-lg">
          <div className="text-4xl mb-2">💀</div>
          <div className="text-lg font-bold text-red-400">探险结束</div>
          <div className="text-sm text-gray-300 mt-1">你在 {state.current_location} 倒下了</div>
        </div>
      )}
    </div>
  );
}