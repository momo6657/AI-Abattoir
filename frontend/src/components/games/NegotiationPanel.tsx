'use client';

interface NegotiationTurn {
  party: 'A' | 'B';
  proposal: string;
  action: 'propose' | 'accept' | 'reject';
  reason: string;
}

interface NegotiationScores {
  party_a_score: number;
  party_b_score: number;
  fairness: number;
  evaluation: string;
}

interface NegotiationPanelProps {
  scenario?: { name: string; description: string; resources?: Record<string, unknown> };
  currentProposal?: string;
  turns: NegotiationTurn[];
  dealReached?: string | null;
  scores?: NegotiationScores | null;
}

const ACTION_CONFIG = {
  propose: { bg: 'bg-blue-900/30', border: 'border-blue-700', icon: '📋', label: '提案', color: 'text-blue-400' },
  accept: { bg: 'bg-green-900/30', border: 'border-green-700', icon: '✅', label: '接受', color: 'text-green-400' },
  reject: { bg: 'bg-red-900/30', border: 'border-red-700', icon: '❌', label: '拒绝', color: 'text-red-400' },
};

export default function NegotiationPanel({
  scenario, currentProposal, turns, dealReached, scores,
}: NegotiationPanelProps) {
  return (
    <div className="space-y-4">
      {/* 场景描述 */}
      {scenario && (
        <div className="p-4 bg-gray-800 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-300">{scenario.name}</h3>
          <p className="text-sm text-gray-400 mt-1">{scenario.description}</p>
          {scenario.resources && (
            <div className="flex gap-2 mt-2 flex-wrap">
              {Object.entries(scenario.resources).map(([key, value]) => (
                <span key={key} className="px-2 py-0.5 bg-gray-700 text-xs text-gray-300 rounded">
                  {key}: {String(value)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 当前提案 */}
      {currentProposal && !dealReached && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-700 rounded-lg">
          <span className="text-xs text-yellow-400">当前提案</span>
          <p className="text-sm text-gray-200 mt-1">{currentProposal}</p>
        </div>
      )}

      {/* 谈判历程 */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {turns.map((turn, i) => {
          const cfg = ACTION_CONFIG[turn.action];
          return (
            <div key={i} className={`${cfg.bg} border ${cfg.border} rounded-lg p-3`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-white">
                  {turn.party === 'A' ? '🅰️ 甲方' : '🅱️ 乙方'}
                </span>
                <span className={`text-xs ${cfg.color}`}>{cfg.icon} {cfg.label}</span>
              </div>
              <p className="text-sm text-gray-200">{turn.proposal}</p>
              {turn.reason && <p className="text-xs text-gray-400 mt-1">理由：{turn.reason}</p>}
            </div>
          );
        })}
      </div>

      {/* 达成协议 */}
      {dealReached && (
        <div className="p-4 bg-green-900/30 border border-green-700 rounded-lg text-center">
          <div className="text-2xl mb-2">🤝</div>
          <div className="text-lg font-bold text-green-400">达成协议</div>
          <p className="text-sm text-gray-200 mt-2">{dealReached}</p>
        </div>
      )}

      {/* 评分 */}
      {scores && (
        <div className="p-4 bg-gray-800 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">独立评估</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-400">{scores.party_a_score}</div>
              <div className="text-xs text-gray-400">甲方</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-purple-400">{scores.fairness}</div>
              <div className="text-xs text-gray-400">公平性</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-400">{scores.party_b_score}</div>
              <div className="text-xs text-gray-400">乙方</div>
            </div>
          </div>
          {scores.evaluation && (
            <p className="text-sm text-gray-400 text-center mt-3">{scores.evaluation}</p>
          )}
        </div>
      )}
    </div>
  );
}