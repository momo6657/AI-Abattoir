'use client';

interface GameControlBarProps {
  status: 'waiting' | 'in_progress' | 'paused' | 'finished' | 'cancelled';
  currentTurn: number;
  maxTurns: number;
  connected: boolean;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onSpeedChange: (speed: number) => void;
}

export default function GameControlBar({
  status, currentTurn, maxTurns, connected,
  onStart, onPause, onResume, onSpeedChange,
}: GameControlBarProps) {
  const speedOptions = [1, 3, 5];
  const [speed, setSpeed] = useState(3);

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed);
    onSpeedChange(newSpeed);
  };

  const statusLabel = {
    waiting: '等待开始',
    in_progress: '进行中',
    paused: '已暂停',
    finished: '已结束',
    cancelled: '已取消',
  }[status] || status;

  const statusColor = {
    waiting: 'bg-blue-500',
    in_progress: 'bg-green-500 animate-pulse',
    paused: 'bg-yellow-500',
    finished: 'bg-gray-500',
    cancelled: 'bg-gray-500',
  }[status] || 'bg-gray-500';

  return (
    <div className="flex items-center justify-between bg-gray-800 rounded-lg p-3 mb-4">
      <div className="flex items-center gap-3">
        <span className={`w-3 h-3 rounded-full ${statusColor}`} />
        <span className="text-sm text-gray-300">{statusLabel}</span>
        <span className="text-sm text-gray-400">
          回合 {currentTurn}/{maxTurns}
        </span>
        <span className={`text-xs ${connected ? 'text-green-400' : 'text-red-400'}`}>
          {connected ? '已连接' : '未连接'}
        </span>
      </div>

      <div className="flex-1 mx-4">
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div
            className="bg-blue-500 rounded-full h-2 transition-all duration-300"
            style={{ width: `${Math.min(100, (currentTurn / maxTurns) * 100)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        {status === 'waiting' && (
          <button onClick={onStart} className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors">
            开始游戏
          </button>
        )}
        {status === 'in_progress' && (
          <button onClick={onPause} className="px-4 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white text-sm rounded-lg transition-colors">
            暂停
          </button>
        )}
        {status === 'paused' && (
          <button onClick={onResume} className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors">
            继续
          </button>
        )}
        {status === 'in_progress' && (
          <div className="flex items-center gap-1 ml-2">
            <span className="text-xs text-gray-400">速度</span>
            {speedOptions.map(s => (
              <button
                key={s}
                onClick={() => handleSpeedChange(s)}
                className={`px-2 py-0.5 text-xs rounded ${speed === s ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
              >
                {s}s
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

import { useState } from 'react';