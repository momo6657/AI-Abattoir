'use client';

import { useState } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import MetricCard from './MetricCard';

interface ShowdownConsoleProps {
  // Config
  showdownUsername: string;
  setShowdownUsername: (v: string) => void;
  showdownPassword: string;
  setShowdownPassword: (v: string) => void;
  showdownAutoLogin: boolean;
  setShowdownAutoLogin: (v: boolean) => void;
  showdownAutoAccept: boolean;
  setShowdownAutoAccept: (v: boolean) => void;
  showdownAutoResearch: boolean;
  setShowdownAutoResearch: (v: boolean) => void;
  showdownRunLimit: number;
  setShowdownRunLimit: (v: number) => void;
  showdownChainRounds: number;
  setShowdownChainRounds: (v: number) => void;
  showdownLoopChains: number;
  setShowdownLoopChains: (v: number) => void;
  showdownProgramFormats: string;
  setShowdownProgramFormats: (v: string) => void;
  showdownMode: 'auto' | 'balanced' | 'aggressive' | 'defensive';
  setShowdownMode: (v: any) => void;
  showdownMissionGoal: 'auto' | 'prepare' | 'queue' | 'ladder' | 'learn';
  setShowdownMissionGoal: (v: any) => void;
  showdownPayload: string;
  setShowdownPayload: (v: string) => void;
  // State
  busy: boolean;
  showdownSession: any;
  showdownPlan: any;
  showdownRunSummary: any;
  showdownMissionPlan: any;
  showdownTacticalBriefing: any;
  showdownMatchupBriefing: any;
  showdownTrainingChain: any;
  showdownTrainingLoop: any;
  showdownTrainingProgramPlan: any;
  showdownTrainingProgram: any;
  showdownTrainingProgramPipeline: any;
  showdownTrainingProgramAutopilot: any;
  showdownMastery: any[];
  showdownTeamKnowledge: any[];
  showdownTeamKnowledgeSummary: any;
  showdownChallengeUser: string | undefined;
  showdownRooms: any[];
  activeLiveReadiness: any;
  activeShowdownLearning: any;
  activeTrainingChainTrend: any;
  showdownTargetPolicy: string;
  selectedFormat: string;
  // Actions
  createShowdownSession: (autoSearch?: boolean) => void;
  startShowdownMission: (plannedRequest?: Record<string, unknown>) => void;
  previewShowdownMissionPlan: () => void;
  previewShowdownTacticalBriefing: () => void;
  previewShowdownTrainingProgram: () => void;
  runShowdownTrainingChain: (plannedRequest?: Record<string, unknown>) => void;
  runShowdownTrainingLoop: () => void;
  runShowdownTrainingProgram: (plannedRequest?: Record<string, unknown>) => void;
  runShowdownTrainingProgramPipeline: (plannedRequest?: Record<string, unknown>) => void;
  runShowdownTrainingProgramAutopilot: (plannedRequest?: Record<string, unknown>) => void;
  startShowdownSearch: () => void;
  connectShowdownSession: () => void;
  refreshShowdownReadiness: () => void;
  refreshShowdownMatchupBriefing: () => void;
  runLiveShowdownOnce: () => void;
  runLiveShowdownUntil: () => void;
  runShowdownAutopilot: () => void;
  runShowdownSupervisor: () => void;
  researchShowdownTeam: () => void;
  cancelShowdownSearch: () => void;
  acceptShowdownChallenge: () => void;
  rejectShowdownChallenge: () => void;
  flushShowdownPending: () => void;
  closeShowdownSession: () => void;
  resetShowdownState: () => void;
  planShowdownChoice: () => void;
  runShowdownSessionStep: () => void;
  executeShowdownNextAction: (action: string) => void;
}

type ConsoleTab = 'session' | 'training' | 'advanced' | 'live';

const TABS: { id: ConsoleTab; label: string; icon: string }[] = [
  { id: 'session', label: '会话', icon: '🔗' },
  { id: 'training', label: '训练', icon: '🎯' },
  { id: 'advanced', label: '高级', icon: '🚀' },
  { id: 'live', label: '实时', icon: '⚡' },
];

function ActionButton({
  onClick,
  disabled,
  label,
  variant = 'secondary',
}: {
  onClick: () => void;
  disabled?: boolean;
  label: string;
  variant?: 'primary' | 'secondary' | 'danger';
}) {
  const cls =
    variant === 'primary'
      ? 'btn-primary'
      : variant === 'danger'
        ? 'bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/30 rounded-lg px-3 py-2 text-xs font-medium transition'
        : 'btn-secondary';
  return (
    <button onClick={onClick} disabled={disabled} className={`${cls} disabled:cursor-not-allowed disabled:opacity-50 text-xs`}>
      {label}
    </button>
  );
}

export default function ShowdownConsole(props: ShowdownConsoleProps) {
  const [activeTab, setActiveTab] = useState<ConsoleTab>('session');
  const {
    showdownUsername, setShowdownUsername,
    showdownPassword, setShowdownPassword,
    showdownAutoLogin, setShowdownAutoLogin,
    showdownAutoAccept, setShowdownAutoAccept,
    showdownAutoResearch, setShowdownAutoResearch,
    showdownRunLimit, setShowdownRunLimit,
    showdownChainRounds, setShowdownChainRounds,
    showdownLoopChains, setShowdownLoopChains,
    showdownProgramFormats, setShowdownProgramFormats,
    showdownMode, setShowdownMode,
    showdownMissionGoal, setShowdownMissionGoal,
    busy, showdownSession, showdownChallengeUser,
  } = props;

  return (
    <section className="card overflow-hidden">
      {/* Header */}
      <div className="border-b border-violet-500/20 bg-gradient-to-r from-violet-500/10 to-indigo-500/10 px-5 py-4">
        <h2 className="text-lg font-semibold text-white">🎮 Showdown 控制台</h2>
        <p className="mt-1 text-xs text-gray-400">创建队伍、搜索天梯、连接 websocket，并有界运行自动选择循环。</p>
      </div>

      {/* Config */}
      <div className="border-b border-border bg-surface-overlay/30 px-5 py-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="text-xs text-gray-500">
            Username
            <input value={showdownUsername} onChange={(e) => setShowdownUsername(e.target.value)}
              className="mt-1 w-full input-field text-sm" />
          </label>
          <label className="text-xs text-gray-500">
            Password
            <input value={showdownPassword} onChange={(e) => setShowdownPassword(e.target.value)}
              type="password" placeholder="optional"
              className="mt-1 w-full input-field text-sm" />
          </label>
          <label className="text-xs text-gray-500">
            Steps
            <input type="number" min={1} max={50} value={showdownRunLimit}
              onChange={(e) => setShowdownRunLimit(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
              className="mt-1 w-full input-field text-sm" />
          </label>
          <label className="text-xs text-gray-500">
            Rounds
            <input type="number" min={1} max={10} value={showdownChainRounds}
              onChange={(e) => setShowdownChainRounds(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
              className="mt-1 w-full input-field text-sm" />
          </label>
        </div>

        <div className="mt-3 flex flex-wrap gap-3">
          <label className="flex items-center gap-2 text-xs text-gray-400">
            <input type="checkbox" checked={showdownAutoLogin} onChange={(e) => setShowdownAutoLogin(e.target.checked)} className="accent-accent" />
            Auto login
          </label>
          <label className="flex items-center gap-2 text-xs text-gray-400">
            <input type="checkbox" checked={showdownAutoAccept} onChange={(e) => setShowdownAutoAccept(e.target.checked)} className="accent-accent" />
            Auto accept
          </label>
          <label className="flex items-center gap-2 text-xs text-gray-400">
            <input type="checkbox" checked={showdownAutoResearch} onChange={(e) => setShowdownAutoResearch(e.target.checked)} className="accent-accent" />
            Auto research
          </label>
        </div>

        {/* Mode & Goal selectors */}
        <div className="mt-3 flex flex-wrap gap-2">
          {(['auto', 'balanced', 'aggressive', 'defensive'] as const).map((mode) => (
            <button key={mode} onClick={() => setShowdownMode(mode)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                showdownMode === mode ? 'bg-accent text-white' : 'bg-surface-overlay text-gray-400 hover:text-white'
              }`}>
              {mode}
            </button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {(['auto', 'prepare', 'queue', 'ladder', 'learn'] as const).map((goal) => (
            <button key={goal} onClick={() => setShowdownMissionGoal(goal)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                showdownMissionGoal === goal ? 'bg-violet-500 text-white' : 'bg-surface-overlay text-gray-400 hover:text-white'
              }`}>
              {goal}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border bg-surface-overlay/20">
        {TABS.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`relative flex items-center gap-2 px-5 py-3 text-sm font-medium transition ${
              activeTab === tab.id
                ? 'text-white bg-surface-overlay/50'
                : 'text-gray-500 hover:text-gray-300'
            }`}>
            <span>{tab.icon}</span>
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute inset-x-0 bottom-0 h-0.5 bg-accent" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {activeTab === 'session' && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <ActionButton onClick={() => props.createShowdownSession(false)} disabled={busy} label="创建会话" variant="primary" />
            <ActionButton onClick={props.connectShowdownSession} disabled={busy} label="连接 PS" />
            <ActionButton onClick={props.closeShowdownSession} disabled={busy || !showdownSession?.session_id} label="关闭连接" />
            <ActionButton onClick={props.resetShowdownState} disabled={busy} label="重置" />
            <ActionButton onClick={props.cancelShowdownSearch} disabled={busy || !showdownSession?.session_id} label="取消搜索" />
            <ActionButton onClick={props.flushShowdownPending} disabled={busy || !showdownSession?.session_id} label="发送待发" />
            <ActionButton onClick={props.acceptShowdownChallenge} disabled={busy || !showdownSession?.session_id || !showdownChallengeUser} label="接受挑战" variant="primary" />
            <ActionButton onClick={props.rejectShowdownChallenge} disabled={busy || !showdownSession?.session_id || !showdownChallengeUser} label="拒绝挑战" />
            <ActionButton onClick={props.researchShowdownTeam} disabled={busy} label="研究队伍" />
          </div>
        )}

        {activeTab === 'training' && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <ActionButton onClick={() => props.startShowdownMission()} disabled={busy} label="启动任务" variant="primary" />
            <ActionButton onClick={props.previewShowdownMissionPlan} disabled={busy} label="预览计划" />
            <ActionButton onClick={props.previewShowdownTacticalBriefing} disabled={busy} label="战术简报" />
            <ActionButton onClick={() => props.runShowdownTrainingChain()} disabled={busy} label="训练链" variant="primary" />
            <ActionButton onClick={props.runShowdownTrainingLoop} disabled={busy} label="训练循环" variant="primary" />
            <ActionButton onClick={() => props.runShowdownTrainingProgram()} disabled={busy} label="多格式训练" variant="primary" />
            <ActionButton onClick={props.previewShowdownTrainingProgram} disabled={busy} label="预览多格式" />
          </div>
        )}

        {activeTab === 'advanced' && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <ActionButton onClick={() => props.runShowdownTrainingProgramPipeline()} disabled={busy} label="训练流水线" variant="primary" />
            <ActionButton onClick={() => props.runShowdownTrainingProgramAutopilot()} disabled={busy} label="训练自动驾驶" variant="primary" />
            <ActionButton onClick={props.runShowdownSupervisor} disabled={busy || !showdownSession?.session_id} label="监督循环" variant="primary" />
          </div>
        )}

        {activeTab === 'live' && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <ActionButton onClick={props.startShowdownSearch} disabled={busy} label="搜索天梯" variant="primary" />
            <ActionButton onClick={props.runLiveShowdownOnce} disabled={busy || !showdownSession?.session_id} label="跑一步" />
            <ActionButton onClick={props.runLiveShowdownUntil} disabled={busy || !showdownSession?.session_id} label="自动运行" variant="primary" />
            <ActionButton onClick={props.runShowdownAutopilot} disabled={busy} label="一键自动" variant="primary" />
            <ActionButton onClick={props.refreshShowdownReadiness} disabled={busy || !showdownSession?.session_id} label="检查就绪" />
            <ActionButton onClick={props.refreshShowdownMatchupBriefing} disabled={busy || !showdownSession?.session_id} label="对局简报" />
          </div>
        )}
      </div>

      {/* Results - Collapsible Panels */}
      <div className="space-y-2 px-4 pb-4">
        {props.activeLiveReadiness && (
          <CollapsiblePanel title="Live Readiness" subtitle={`${props.activeLiveReadiness.status} · ${props.activeLiveReadiness.score ?? 0}/100`}
            color="border-sky-500/30 bg-sky-500/5" defaultOpen>
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Blocked" value={props.activeLiveReadiness.blocked_count || 0} compact />
              <MetricCard label="Actions" value={props.activeLiveReadiness.action_required_count || 0} compact />
              <MetricCard label="Ready" value={props.activeLiveReadiness.ready_for_ladder ? 'yes' : 'no'} compact />
            </div>
            {props.activeLiveReadiness.recommendation && (
              <p className="mt-2 text-xs text-gray-400">{props.activeLiveReadiness.recommendation}</p>
            )}
          </CollapsiblePanel>
        )}

        {props.showdownTacticalBriefing && (
          <CollapsiblePanel title="Tactical Briefing" subtitle={`${props.showdownTacticalBriefing.mode} · ${props.showdownTacticalBriefing.tactical_plan?.confidence || 'low'}`}
            color="border-violet-500/30 bg-violet-500/5">
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Mastery" value={props.showdownTacticalBriefing.mastery_score != null ? Number(props.showdownTacticalBriefing.mastery_score).toFixed(0) : '-'} compact />
              <MetricCard label="Samples" value={props.showdownTacticalBriefing.learning_profile?.battles || 0} compact />
            </div>
            {props.showdownTacticalBriefing.tactical_plan?.opening_plan && (
              <p className="mt-2 text-xs text-violet-200">{props.showdownTacticalBriefing.tactical_plan.opening_plan}</p>
            )}
          </CollapsiblePanel>
        )}

        {props.showdownMatchupBriefing && (
          <CollapsiblePanel title="Matchup Briefing" subtitle={`${props.showdownMatchupBriefing.matchup_plan?.confidence || 'low'} · ${props.showdownMatchupBriefing.sides?.opponent_username || 'opponent'}`}
            color="border-rose-500/30 bg-rose-500/5">
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Opponent" value={(props.showdownMatchupBriefing.opponent?.species || []).length} compact />
              <MetricCard label="Threats" value={(props.showdownMatchupBriefing.threats || []).length} compact />
            </div>
          </CollapsiblePanel>
        )}

        {props.showdownMissionPlan && (
          <CollapsiblePanel title="Mission Plan" subtitle={`${props.showdownMissionPlan.mission_goal} · ${props.showdownMissionPlan.mission_goal_source}`}
            color="border-accent/30 bg-accent/5">
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Mode" value={props.showdownMissionPlan.mode || '-'} compact />
              <MetricCard label="Actions" value={(props.showdownMissionPlan.executable_plan_actions || props.showdownMissionPlan.allowed_actions || []).length} compact />
            </div>
          </CollapsiblePanel>
        )}

        {props.showdownTrainingChain && (
          <CollapsiblePanel title="Training Chain" subtitle={`${props.showdownTrainingChain.completed_rounds}/${props.showdownTrainingChain.requested_rounds} · ${props.showdownTrainingChain.stop_reason}`}
            color="border-emerald-500/30 bg-emerald-500/5">
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Mastery" value={props.showdownTrainingChain.mastery_score != null ? Number(props.showdownTrainingChain.mastery_score).toFixed(0) : '-'} compact />
              <MetricCard label="Rounds" value={props.showdownTrainingChain.completed_rounds || 0} compact />
              <MetricCard label="Trend" value={props.showdownTrainingChain.progress?.direction || '-'} compact />
            </div>
          </CollapsiblePanel>
        )}

        {props.showdownTrainingLoop && (
          <CollapsiblePanel title="Training Loop" subtitle={`${props.showdownTrainingLoop.completed_chains}/${props.showdownTrainingLoop.requested_chain_limit} · ${props.showdownTrainingLoop.stop_reason}`}
            color="border-lime-500/30 bg-lime-500/5">
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Chains" value={props.showdownTrainingLoop.completed_chains || 0} compact />
              <MetricCard label="Rounds" value={props.showdownTrainingLoop.total_completed_rounds || 0} compact />
            </div>
          </CollapsiblePanel>
        )}

        {props.showdownTrainingProgramPlan && (
          <CollapsiblePanel title="Program Plan" subtitle={`${props.showdownTrainingProgramPlan.planned_format_count}/${props.showdownTrainingProgramPlan.requested_format_limit} · ${props.showdownTrainingProgramPlan.status}`}
            color="border-sky-500/30 bg-sky-500/5">
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Formats" value={props.showdownTrainingProgramPlan.planned_format_count || 0} compact />
              <MetricCard label="Samples" value={props.showdownTrainingProgramPlan.total_existing_samples || 0} compact />
              <MetricCard label="Lowest" value={Number(props.showdownTrainingProgramPlan.lowest_mastery_score || 0).toFixed(0)} compact />
            </div>
          </CollapsiblePanel>
        )}

        {props.showdownTrainingProgramPipeline && (
          <CollapsiblePanel title="Training Pipeline" subtitle={`${props.showdownTrainingProgramPipeline.completed_stages}/${props.showdownTrainingProgramPipeline.requested_stage_limit} · ${props.showdownTrainingProgramPipeline.pipeline_health?.status || props.showdownTrainingProgramPipeline.stop_reason}`}
            color="border-violet-500/30 bg-violet-500/5">
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Stages" value={props.showdownTrainingProgramPipeline.completed_stages || 0} compact />
              <MetricCard label="Blocked" value={props.showdownTrainingProgramPipeline.pipeline_health?.blocked_stage_count || 0} compact />
            </div>
          </CollapsiblePanel>
        )}

        {props.showdownTrainingProgramAutopilot && (
          <CollapsiblePanel title="Training Autopilot" subtitle={`${props.showdownTrainingProgramAutopilot.completed_cycles}/${props.showdownTrainingProgramAutopilot.requested_cycle_limit} · ${props.showdownTrainingProgramAutopilot.autopilot_health?.status || props.showdownTrainingProgramAutopilot.stop_reason}`}
            color="border-fuchsia-500/30 bg-fuchsia-500/5">
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Cycles" value={props.showdownTrainingProgramAutopilot.completed_cycles || 0} compact />
              <MetricCard label="Stages" value={props.showdownTrainingProgramAutopilot.autopilot_health?.total_stages || 0} compact />
              <MetricCard label="Rounds" value={props.showdownTrainingProgramAutopilot.autopilot_health?.total_completed_rounds || 0} compact />
            </div>
          </CollapsiblePanel>
        )}

        {/* Decision & Run Summary */}
        {props.showdownPlan && (
          <CollapsiblePanel title="Showdown Decision" subtitle={props.showdownPlan.decision_type}
            color="border-sky-500/20 bg-sky-500/5">
            <div className="break-all rounded bg-black/30 p-2 font-mono text-xs text-gray-100">
              {props.showdownPlan.command || 'waiting'}
            </div>
            <p className="mt-2 text-xs text-gray-400">{props.showdownPlan.reason}</p>
          </CollapsiblePanel>
        )}

        {props.showdownRunSummary && (
          <CollapsiblePanel title="Run Summary" subtitle={`#${props.showdownRunSummary.run_number ?? '-'} · ${props.showdownRunSummary.stopped_reason || props.showdownRunSummary.status}`}
            color="border-border bg-black/10">
            <div className="grid grid-cols-3 gap-2">
              <MetricCard label="Steps" value={props.showdownRunSummary.step_count ?? 0} compact />
              <MetricCard label="Sent" value={props.showdownRunSummary.total_sent_count ?? 0} compact />
              <MetricCard label="Decisions" value={props.showdownRunSummary.decision_count ?? 0} compact />
            </div>
          </CollapsiblePanel>
        )}

        {/* Mastery Ranking */}
        {props.showdownMastery.length > 0 && (
          <CollapsiblePanel title="Mastery Ranking" subtitle={`${props.showdownMastery.length} entries`}
            color="border-amber-500/20 bg-amber-500/5">
            <div className="space-y-1.5">
              {props.showdownMastery.slice(0, 5).map((entry: any, index: number) => (
                <div key={entry.username_key || index} className="flex items-center justify-between rounded border border-border bg-black/20 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-amber-300">#{index + 1}</span>
                    <span className="text-sm text-gray-200">{entry.username}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-white">{Number(entry.mastery_score || 0).toFixed(0)}</div>
                    <div className="text-[10px] text-gray-500">{entry.battles} battles · {entry.win_rate ?? 0}% win</div>
                  </div>
                </div>
              ))}
            </div>
          </CollapsiblePanel>
        )}
      </div>
    </section>
  );
}
