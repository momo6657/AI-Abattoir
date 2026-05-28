'use client';

interface DebateRound {
  phase: string;
  side: 'pro' | 'con';
  content: string;
}

interface DebateScores {
  pro_arguments?: number;
  pro_logic?: number;
  pro_expression?: number;
  con_arguments?: number;
  con_logic?: number;
  con_expression?: number;
  pro_total?: number;
  con_total?: number;
  winner?: string;
  reason?: string;
}

interface DebatePanelProps {
  topic: string;
  rounds: DebateRound[];
  currentPhase: string;
  scores?: DebateScores | null;
}

function ScoreBar({ label, value, side }: { label: string; value: number; side: 'pro' | 'con' }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-8">{label}</span>
      <div className="flex-1 bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${side === 'pro' ? 'bg-blue-500' : 'bg-orange-500'}`}
          style={{ width: `${(value / 10) * 100}%` }}
        />
      </div>
      <span className="text-xs text-gray-300 w-6 text-right">{value}</span>
    </div>
  );
}

export default function DebatePanel({ topic, rounds, currentPhase, scores }: DebatePanelProps) {
  const proRounds = rounds.filter(r => r.side === 'pro');
  const conRounds = rounds.filter(r => r.side === 'con');
  const phases = ['opening', 'cross', 'closing', 'result'];

  return (
    <div className="space-y-4">
      {/* 辩题 */}
      <div className="text-center p-4 bg-gray-800 rounded-lg">
        <span className="text-sm text-gray-400">辩论主题</span>
        <h2 className="text-lg font-bold text-white mt-1">{topic}</h2>
      </div>

      {/* 阶段指示器 */}
      <div className="flex items-center justify-center gap-2">
        {phases.map((phase, i) => {
          const isActive = currentPhase === phase;
          const isPast = phases.indexOf(currentPhase) > i;
          return (
            <div key={phase} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                isActive ? 'bg-blue-600 text-white' :
                isPast ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-400'
              }`}>
                {i + 1}
              </div>
              <span className="text-xs text-gray-400 hidden sm:inline">
                {phase === 'opening' ? '立论' : phase === 'cross' ? '质询' : phase === 'closing' ? '总结' : '评分'}
              </span>
              {i < 3 && <div className="w-8 h-0.5 bg-gray-700" />}
            </div>
          );
        })}
      </div>

      {/* 正反方分栏 */}
      <div className="grid grid-cols-2 gap-4">
        {/* 正方 */}
        <div className="space-y-3">
          <div className="text-center py-2 bg-blue-900/30 border border-blue-700 rounded-lg">
            <span className="text-blue-400 font-semibold">正方</span>
          </div>
          {proRounds.map((round, i) => (
            <div key={i} className="bg-gray-800 rounded-lg p-3">
              <span className="text-xs text-gray-400">
                {round.phase === 'opening' ? '立论' :
                 round.phase === 'cross_examination' ? '质询' :
                 round.phase === 'cross_response' ? '回应' : '总结'}
              </span>
              <p className="text-sm text-gray-200 mt-1">{round.content}</p>
            </div>
          ))}
          {scores && (
            <div className="bg-gray-800 rounded-lg p-3">
              <h4 className="text-xs text-gray-400 mb-2">评分</h4>
              <div className="space-y-2">
                <ScoreBar label="论据" value={scores.pro_arguments || 0} side="pro" />
                <ScoreBar label="逻辑" value={scores.pro_logic || 0} side="pro" />
                <ScoreBar label="表达" value={scores.pro_expression || 0} side="pro" />
              </div>
              <div className="text-center mt-2 text-sm text-blue-400 font-bold">
                总分：{scores.pro_total || 0}
              </div>
            </div>
          )}
        </div>

        {/* 反方 */}
        <div className="space-y-3">
          <div className="text-center py-2 bg-orange-900/30 border border-orange-700 rounded-lg">
            <span className="text-orange-400 font-semibold">反方</span>
          </div>
          {conRounds.map((round, i) => (
            <div key={i} className="bg-gray-800 rounded-lg p-3">
              <span className="text-xs text-gray-400">
                {round.phase === 'opening' ? '立论' :
                 round.phase === 'cross_examination' ? '质询' :
                 round.phase === 'cross_response' ? '回应' : '总结'}
              </span>
              <p className="text-sm text-gray-200 mt-1">{round.content}</p>
            </div>
          ))}
          {scores && (
            <div className="bg-gray-800 rounded-lg p-3">
              <h4 className="text-xs text-gray-400 mb-2">评分</h4>
              <div className="space-y-2">
                <ScoreBar label="论据" value={scores.con_arguments || 0} side="con" />
                <ScoreBar label="逻辑" value={scores.con_logic || 0} side="con" />
                <ScoreBar label="表达" value={scores.con_expression || 0} side="con" />
              </div>
              <div className="text-center mt-2 text-sm text-orange-400 font-bold">
                总分：{scores.con_total || 0}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 获胜方 */}
      {scores?.winner && (
        <div className={`text-center p-4 rounded-lg border-2 ${
          scores.winner === '正方' ? 'bg-blue-900/30 border-blue-700' : 'bg-orange-900/30 border-orange-700'
        }`}>
          <div className="text-lg font-bold text-white">{scores.winner}获胜</div>
          {scores.reason && <div className="text-sm text-gray-300 mt-1">{scores.reason}</div>}
        </div>
      )}
    </div>
  );
}