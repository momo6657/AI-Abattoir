'use client';

interface TextAdventureStateProps {
  hp?: number;
  maxHp?: number;
  inventory?: string[];
  currentLocation?: string;
  exploredLocations?: string[];
  scene?: string;
  lastAction?: string;
  lastResult?: string;
  lastHpChange?: number;
  lastItem?: string;
  turn?: number;
}

export default function TextAdventureState({
  hp = 100,
  maxHp = 100,
  inventory = [],
  currentLocation,
  exploredLocations = [],
  scene,
  lastAction,
  lastResult,
  lastHpChange,
  lastItem,
  turn,
}: TextAdventureStateProps) {
  const hpPct = maxHp > 0 ? Math.max(0, Math.min(100, (hp / maxHp) * 100)) : 0;
  const hpColor = hpPct > 60 ? 'bg-green-500' : hpPct > 30 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">🗺️ 文字冒险</span>
        {turn != null && <span className="text-xs text-gray-400">回合 {turn}</span>}
      </div>

      {/* HP Bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">❤️ 生命值</span>
          <span className={hpPct > 30 ? 'text-gray-200' : 'text-red-400'}>
            {hp} / {maxHp}
          </span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full ${hpColor} transition-all duration-500`}
            style={{ width: `${hpPct}%` }}
          />
        </div>
        {lastHpChange != null && lastHpChange !== 0 && (
          <div className={`text-xs ${lastHpChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {lastHpChange > 0 ? '+' : ''}{lastHpChange} HP
          </div>
        )}
      </div>

      {/* Location */}
      {currentLocation && (
        <div className="bg-gray-700/50 rounded p-2 text-xs">
          <span className="text-gray-400">📍 位置：</span>
          <span className="text-blue-300">{currentLocation}</span>
        </div>
      )}

      {/* Scene */}
      {scene && (
        <div className="bg-gray-800 rounded p-2 text-xs text-gray-300 leading-relaxed">
          {scene}
        </div>
      )}

      {/* Last Action & Result */}
      {lastAction && (
        <div className="bg-indigo-900/30 rounded p-2 text-xs space-y-1">
          <div>
            <span className="text-gray-400">选择：</span>
            <span className="text-indigo-300">{lastAction}</span>
          </div>
          {lastResult && (
            <div>
              <span className="text-gray-400">结果：</span>
              <span className="text-gray-200">{lastResult}</span>
            </div>
          )}
          {lastItem && lastItem.toUpperCase() !== 'NONE' && (
            <div>
              <span className="text-gray-400">获得：</span>
              <span className="text-yellow-300">{lastItem}</span>
            </div>
          )}
        </div>
      )}

      {/* Inventory */}
      {inventory.length > 0 && (
        <div className="space-y-1">
          <span className="text-xs text-gray-400">🎒 物品 ({inventory.length})</span>
          <div className="flex flex-wrap gap-1">
            {inventory.map((item, idx) => (
              <span
                key={idx}
                className="bg-yellow-900/30 text-yellow-300 px-1.5 py-0.5 rounded text-[10px]"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Explored Locations */}
      {exploredLocations.length > 1 && (
        <div className="space-y-1">
          <span className="text-xs text-gray-400">🗺️ 已探索 ({exploredLocations.length})</span>
          <div className="flex flex-wrap gap-1">
            {exploredLocations.map((loc, idx) => (
              <span
                key={idx}
                className={`px-1.5 py-0.5 rounded text-[10px] ${
                  loc === currentLocation
                    ? 'bg-blue-900/50 text-blue-300'
                    : 'bg-gray-800 text-gray-500'
                }`}
              >
                {loc}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
