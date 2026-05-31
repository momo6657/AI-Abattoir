'use client';

interface NegotiationTrackerProps {
  phase?: 'negotiating' | 'accepted' | 'rejected';
  proposals?: Array<{
    player: string;
    proposal: string;
    accepted?: boolean;
  }>;
  currentProposal?: string;
  proposedBy?: string;
  scores?: {
    player1?: number;
    player2?: number;
    fairness?: number;
  };
}

const PHASE_CONFIG = {
  negotiating: { label: '谈判中', color: 'text-yellow-400', bg: 'bg-yellow-900/20', border: 'border-yellow-700' },
  accepted: { label: '已接受', color: 'text-green-400', bg: 'bg-green-900/30', border: 'border-green-700' },
  rejected: { label: '已拒绝', color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-700' },
};

export default function NegotiationTracker({
  phase,
  proposals,
  currentProposal,
  proposedBy,
  scores,
}: NegotiationTrackerProps) {
  const phaseCfg = phase ? PHASE_CONFIG[phase] : null;

  return (
    <div className="space-y-4">
      {/* 当前阶段 */}
      {phaseCfg && (
        <div className={`text-center py-2 ${phaseCfg.bg} border ${phaseCfg.border} rounded-lg`}>
          <span className={`${phaseCfg.color} font-semibold`}>{phaseCfg.label}</span>
        </div>
      )}

      {/* 当前提案 */}
      {currentProposal && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-700 rounded-lg">
          <span className="text-xs text-yellow-400">当前提案</span>
          {proposedBy && (
            <span className="text-xs text-gray-400 ml-2">— {proposedBy}</span>
          )}
          <p className="text-sm text-gray-200 mt-1">{currentProposal}</p>
        </div>
      )}

      {/* 提案历史 */}
      {proposals && proposals.length > 0 && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          <h3 className="text-sm font-semibold text-gray-300">提案历史</h3>
          {proposals.map((item, i) => (
            <div
              key={i}
              className={`border rounded-lg p-3 ${
                item.accepted === true
                  ? 'bg-green-900/20 border-green-700'
                  : item.accepted === false
                    ? 'bg-red-900/20 border-red-700'
                    : 'bg-gray-800 border-gray-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-white">{item.player}</span>
                {item.accepted !== undefined && (
                  <span
                    className={`text-xs ${
                      item.accepted ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {item.accepted ? '✅ 已接受' : '❌ 已拒绝'}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-200">{item.proposal}</p>
            </div>
          ))}
        </div>
      )}

      {/* 最终评分 */}
      {scores && (
        <div className="p-4 bg-gray-800 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">评分</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-400">{scores.player1 ?? 0}</div>
              <div className="text-xs text-gray-400">玩家 1</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-purple-400">{scores.fairness ?? 0}</div>
              <div className="text-xs text-gray-400">公平性</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-400">{scores.player2 ?? 0}</div>
              <div className="text-xs text-gray-400">玩家 2</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
