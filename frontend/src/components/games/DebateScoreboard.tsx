'use client';

interface DebateScoreboardProps {
  topic?: string;
  phase?: 'opening' | 'cross' | 'closing' | 'result';
  proOpening?: string;
  conOpening?: string;
  proCross?: string;
  conCross?: string;
  proClosing?: string;
  conClosing?: string;
  proScores?: {
    arguments?: number;
    logic?: number;
    expression?: number;
  };
  conScores?: {
    arguments?: number;
    logic?: number;
    expression?: number;
  };
  winner?: 'pro' | 'con' | null;
}

const PHASES: { key: DebateScoreboardProps['phase']; label: string }[] = [
  { key: 'opening', label: '立论' },
  { key: 'cross', label: '质询' },
  { key: 'closing', label: '总结' },
  { key: 'result', label: '评分' },
];

function ScoreBar({ label, value, side }: { label: string; value: number; side: 'pro' | 'con' }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-8">{label}</span>
      <div className="flex-1 bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${side === 'pro' ? 'bg-blue-500' : 'bg-orange-500'}`}
          style={{ width: `${Math.min((value / 10) * 100, 100)}%` }}
        />
      </div>
      <span className="text-xs text-gray-300 w-6 text-right">{value}</span>
    </div>
  );
}

function SideCard({
  side,
  opening,
  cross,
  closing,
  scores,
}: {
  side: 'pro' | 'con';
  opening?: string;
  cross?: string;
  closing?: string;
  scores?: DebateScoreboardProps['proScores'];
}) {
  const isPro = side === 'pro';
  const borderColor = isPro ? 'border-blue-700' : 'border-orange-700';
  const bgColor = isPro ? 'bg-blue-900/30' : 'bg-orange-900/30';
  const textColor = isPro ? 'text-blue-400' : 'text-orange-400';
  const label = isPro ? '正方' : '反方';

  const sections = [
    { title: '立论', content: opening },
    { title: '质询', content: cross },
    { title: '总结', content: closing },
  ];

  return (
    <div className="space-y-3">
      <div className={`text-center py-2 ${bgColor} border ${borderColor} rounded-lg`}>
        <span className={`${textColor} font-semibold`}>{label}</span>
      </div>

      {sections.map(
        ({ title, content }) =>
          content && (
            <div key={title} className="bg-gray-800 rounded-lg p-3">
              <span className="text-xs text-gray-400">{title}</span>
              <p className="text-sm text-gray-200 mt-1">{content}</p>
            </div>
          ),
      )}

      {scores && (
        <div className="bg-gray-800 rounded-lg p-3">
          <h4 className="text-xs text-gray-400 mb-2">评分</h4>
          <div className="space-y-2">
            <ScoreBar label="论据" value={scores.arguments ?? 0} side={side} />
            <ScoreBar label="逻辑" value={scores.logic ?? 0} side={side} />
            <ScoreBar label="表达" value={scores.expression ?? 0} side={side} />
          </div>
          <div className={`text-center mt-2 text-sm ${textColor} font-bold`}>
            总分：{(scores.arguments ?? 0) + (scores.logic ?? 0) + (scores.expression ?? 0)}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DebateScoreboard({
  topic,
  phase,
  proOpening,
  conOpening,
  proCross,
  conCross,
  proClosing,
  conClosing,
  proScores,
  conScores,
  winner,
}: DebateScoreboardProps) {
  const phaseIndex = PHASES.findIndex((p) => p.key === phase);

  return (
    <div className="space-y-4">
      {/* 辩题 */}
      {topic && (
        <div className="text-center p-4 bg-gray-800 rounded-lg">
          <span className="text-sm text-gray-400">辩论主题</span>
          <h2 className="text-lg font-bold text-white mt-1">{topic}</h2>
        </div>
      )}

      {/* 阶段指示器 */}
      {phase && (
        <div className="flex items-center justify-center gap-2">
          {PHASES.map((p, i) => {
            const isActive = phase === p.key;
            const isPast = phaseIndex > i;
            return (
              <div key={p.key} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : isPast
                        ? 'bg-green-600 text-white'
                        : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  {i + 1}
                </div>
                <span className="text-xs text-gray-400 hidden sm:inline">{p.label}</span>
                {i < PHASES.length - 1 && <div className="w-8 h-0.5 bg-gray-700" />}
              </div>
            );
          })}
        </div>
      )}

      {/* 正反方分栏 */}
      <div className="grid grid-cols-2 gap-4">
        <SideCard
          side="pro"
          opening={proOpening}
          cross={proCross}
          closing={proClosing}
          scores={proScores}
        />
        <SideCard
          side="con"
          opening={conOpening}
          cross={conCross}
          closing={conClosing}
          scores={conScores}
        />
      </div>

      {/* 获胜方 */}
      {winner && (
        <div
          className={`text-center p-4 rounded-lg border-2 ${
            winner === 'pro' ? 'bg-blue-900/30 border-blue-700' : 'bg-orange-900/30 border-orange-700'
          }`}
        >
          <div className="text-2xl mb-2">🏆</div>
          <div className="text-lg font-bold text-white">
            {winner === 'pro' ? '正方' : '反方'}获胜
          </div>
        </div>
      )}
    </div>
  );
}
