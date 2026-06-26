'use client';

import { useEffect, useMemo, useState } from 'react';
import BattleField from './components/BattleField';
import TeamManager from './components/TeamManager';
import MoveSelector from './components/MoveSelector';
import ShowdownConsole from './components/ShowdownConsole';
import { agentsApi, modelsApi, pokemonApi, resolveWebSocketURL } from '@/lib/api';

const MODEL_NAME = 'Pokemon Local Policy';
const RED_AGENT = '红方训练师';
const BLUE_AGENT = '蓝方训练师';
const SAMPLE_SHOWDOWN_PAYLOAD =
  '>battle-gen9vgc-demo\n|request|{"rqid":1,"active":[{"moves":[{"id":"protect","target":"self","pp":16},{"id":"moonblast","target":"normal","basePower":95,"pp":15}]}]}';

type SetupState = {
  model?: any;
  redAgent?: any;
  blueAgent?: any;
  redTeam?: any;
  blueTeam?: any;
};

type PokemonFormat = {
  id: string;
  name: string;
  name_zh: string;
  showdown_format: string;
  battle_type: string;
  team_size: number;
  active_pokemon: number;
  requires_team: boolean;
  template_format?: string | null;
};

function formatLogEntry(entry: any): string {
  if (!entry) return 'Unknown event';
  const data = entry.data || {};
  if (entry.event === 'move') return `T${entry.turn}: ${data.attacker || data.pokemon} used ${data.move}`;
  if (entry.event === 'damage') return `T${entry.turn}: ${data.target} took ${data.damage} damage`;
  if (entry.event === 'faint') return `T${entry.turn}: ${data.pokemon} fainted`;
  if (entry.event === 'switch') return `T${entry.turn}: Player ${data.player} switched ${data.from} to ${data.to}`;
  return `T${entry.turn ?? '-'}: ${entry.event}`;
}

function chooseMoveIndex(pokemon: any): number {
  const moves = pokemon?.moves || [];
  const damagingIndex = moves.findIndex((move: any) => {
    if (typeof move === 'string') return !['Protect', 'Tailwind', 'Trick Room', 'Helping Hand', 'Taunt'].includes(move);
    return move?.category !== 'status' && Number(move?.power || 0) > 0;
  });
  return damagingIndex >= 0 ? damagingIndex : 0;
}

function buildActions(active: any[], targetPlayer: 1 | 2, opponentActive: any[]) {
  const targetCount = Math.max(1, opponentActive?.length || 1);
  return (active || [])
    .map((pokemon, index) => {
      const targetSlot = Math.min(index, targetCount - 1);
      const targetIndex = opponentActive?.[targetSlot]?.position ?? targetSlot;
      return {
        pokemon_index: pokemon?.position ?? index,
        action_type: 'move',
        move_index: chooseMoveIndex(pokemon),
        target: [targetPlayer, targetIndex],
      };
    })
    .filter((_, index) => !active[index]?.is_fainted);
}

export default function PokemonBattlePage() {
  const [setup, setSetup] = useState<SetupState>({});
  const [battleId, setBattleId] = useState<string | null>(null);
  const [battleState, setBattleState] = useState<any>(null);
  const [speciesCount, setSpeciesCount] = useState(0);
  const [moveCount, setMoveCount] = useState(0);
  const [history, setHistory] = useState<any[]>([]);
  const [formats, setFormats] = useState<PokemonFormat[]>([]);
  const [formatCapabilities, setFormatCapabilities] = useState<any>(null);
  const [selectedFormat, setSelectedFormat] = useState('vgc2024');
  const [analysis, setAnalysis] = useState<any>(null);
  const [knowledgeQuery, setKnowledgeQuery] = useState('Incineroar');
  const [knowledge, setKnowledge] = useState<any>(null);
  const [showdownTeamKnowledge, setShowdownTeamKnowledge] = useState<any[]>([]);
  const [showdownTeamKnowledgeSummary, setShowdownTeamKnowledgeSummary] = useState<any>(null);
  const [showdownPayload, setShowdownPayload] = useState(SAMPLE_SHOWDOWN_PAYLOAD);
  const [showdownUsername, setShowdownUsername] = useState('PokemonBot');
  const [showdownPassword, setShowdownPassword] = useState('');
  const [showdownAutoLogin, setShowdownAutoLogin] = useState(true);
  const [showdownAutoAccept, setShowdownAutoAccept] = useState(false);
  const [showdownAutoResearch, setShowdownAutoResearch] = useState(false);
  const [showdownRunLimit, setShowdownRunLimit] = useState(10);
  const [showdownChainRounds, setShowdownChainRounds] = useState(2);
  const [showdownLoopChains, setShowdownLoopChains] = useState(3);
  const [showdownProgramFormats, setShowdownProgramFormats] = useState('gen9randombattle, gen9ou');
  const [showdownMode, setShowdownMode] = useState<'auto' | 'balanced' | 'aggressive' | 'defensive'>('auto');
  const [showdownMissionGoal, setShowdownMissionGoal] = useState<'auto' | 'prepare' | 'queue' | 'ladder' | 'learn'>('auto');
  const [showdownMissionPlan, setShowdownMissionPlan] = useState<any>(null);
  const [showdownTacticalBriefing, setShowdownTacticalBriefing] = useState<any>(null);
  const [showdownMatchupBriefing, setShowdownMatchupBriefing] = useState<any>(null);
  const [showdownTrainingChain, setShowdownTrainingChain] = useState<any>(null);
  const [showdownTrainingLoop, setShowdownTrainingLoop] = useState<any>(null);
  const [showdownTrainingProgramPlan, setShowdownTrainingProgramPlan] = useState<any>(null);
  const [showdownTrainingProgram, setShowdownTrainingProgram] = useState<any>(null);
  const [showdownTrainingProgramPipeline, setShowdownTrainingProgramPipeline] = useState<any>(null);
  const [showdownTrainingProgramAutopilot, setShowdownTrainingProgramAutopilot] = useState<any>(null);
  const [showdownPlan, setShowdownPlan] = useState<any>(null);
  const [showdownSession, setShowdownSession] = useState<any>(null);
  const [showdownAnalysis, setShowdownAnalysis] = useState<any>(null);
  const [showdownLearning, setShowdownLearning] = useState<any>(null);
  const [showdownMastery, setShowdownMastery] = useState<any[]>([]);
  const [showdownRunSummary, setShowdownRunSummary] = useState<any>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsURL = useMemo(
    () => (battleId ? resolveWebSocketURL(`/ws/pokemon/battle/${battleId}`) : ''),
    [battleId]
  );
  const selectedFormatInfo = useMemo(
    () => formats.find((format) => format.id === selectedFormat) || formats[0],
    [formats, selectedFormat]
  );
  const activeFormatCapability = useMemo(
    () => (formatCapabilities?.formats || []).find((item: any) => item.format?.id === selectedFormat),
    [formatCapabilities, selectedFormat]
  );
  const showdownTargetPolicy = selectedFormatInfo?.active_pokemon === 1 ? 'no target' : 'targeted';
  const showdownChallengeUsers = Object.keys(showdownSession?.challenges?.challengesFrom || {});
  const showdownChallengeUser = showdownChallengeUsers[0];
  const showdownRooms = Object.values(showdownSession?.room_details || {}) as any[];
  const activeShowdownLearning = showdownLearning || showdownSession?.learning_profile || null;
  const activeMasteryEntry = showdownMastery.find((entry) =>
    String(entry.username || '').toLowerCase() === String(showdownUsername || '').toLowerCase()
  );
  const showdownTrainingPlan =
    showdownSession?.last_mission_summary?.training_plan ||
    activeShowdownLearning?.training_plan ||
    showdownSession?.learning_profile?.training_plan ||
    null;
  const showdownPolicyEvaluation = activeShowdownLearning?.policy_evaluation || null;
  const activeShowdownTrainingChain = showdownTrainingChain || showdownSession?.last_training_chain_summary || null;
  const activeShowdownTrainingLoop = showdownTrainingLoop || null;
  const activeShowdownTrainingProgramPlan = showdownTrainingProgramPlan || null;
  const activeShowdownTrainingProgram = showdownTrainingProgram || null;
  const activeShowdownTrainingProgramPipeline = showdownTrainingProgramPipeline || null;
  const activeShowdownTrainingProgramAutopilot = showdownTrainingProgramAutopilot || null;
  const activeTrainingChainTrend = showdownSession?.training_chain_trend || showdownTrainingChain?.final_session?.training_chain_trend || null;
  const activeLiveReadiness = showdownSession?.live_readiness || null;

  useEffect(() => {
    refreshOverview();
  }, []);

  useEffect(() => {
    refreshShowdownMastery();
  }, [selectedFormat]);

  function addMessage(message: string) {
    setMessages((prev) => [message, ...prev].slice(0, 14));
  }

  function applyShowdownSession(session: any, runSummary?: any) {
    if (!session) return;
    setShowdownSession(session);
    setShowdownRunSummary(runSummary || session.last_run_summary || null);
  }

  function resetShowdownState() {
    setShowdownSession(null);
    setShowdownAnalysis(null);
    setShowdownLearning(null);
    setShowdownPlan(null);
    setShowdownMissionPlan(null);
    setShowdownTacticalBriefing(null);
    setShowdownMatchupBriefing(null);
    setShowdownTrainingChain(null);
    setShowdownTrainingLoop(null);
    setShowdownTrainingProgramPlan(null);
    setShowdownTrainingProgram(null);
    setShowdownTrainingProgramPipeline(null);
    setShowdownTrainingProgramAutopilot(null);
    setShowdownRunSummary(null);
    setShowdownTeamKnowledge([]);
    setShowdownTeamKnowledgeSummary(null);
  }

  async function refreshOverview() {
    try {
      const [speciesRes, movesRes, historyRes, formatsRes, masteryRes, capabilitiesRes] = await Promise.all([
        pokemonApi.listSpecies(),
        pokemonApi.listMoves(),
        pokemonApi.getHistory(8),
        pokemonApi.listFormats(),
        pokemonApi.listShowdownMastery(selectedFormat, 5),
        pokemonApi.listShowdownFormatCapabilities(showdownUsername || 'PokemonBot'),
      ]);
      setSpeciesCount(speciesRes.data.length || 0);
      setMoveCount(movesRes.data.length || 0);
      setHistory(historyRes.data || []);
      setShowdownMastery(masteryRes.data || []);
      setFormatCapabilities(capabilitiesRes.data || null);
      const nextFormats = formatsRes.data || [];
      setFormats(nextFormats);
      if (nextFormats.length && !nextFormats.some((format: PokemonFormat) => format.id === selectedFormat)) {
        setSelectedFormat(nextFormats[0].id);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '无法读取 Pokemon 模块状态');
    }
  }

  async function refreshShowdownMastery() {
    try {
      const mastery = (await pokemonApi.listShowdownMastery(selectedFormat, 5)).data || [];
      setShowdownMastery(mastery);
    } catch {
      setShowdownMastery([]);
    }
  }

  async function getOrCreateModel() {
    const models = (await modelsApi.list()).data || [];
    const existing = models.find((model: any) => model.name === MODEL_NAME);
    if (existing) return existing;
    return (await modelsApi.create({
      name: MODEL_NAME,
      provider: 'local',
      model_id: 'pokemon-local-policy',
      config: { role: 'pokemon-battle-simulation' },
    })).data;
  }

  async function getOrCreateAgent(name: string, modelId: string, style: string) {
    const agents = (await agentsApi.list()).data || [];
    const existing = agents.find((agent: any) => agent.name === name);
    if (existing) return existing;
    return (await agentsApi.create({
      name,
      description: `${style} 的宝可梦训练智能体，用于本地 VGC 训练。`,
      model_id: modelId,
      profile: {
        persona: `你是${name}，目标是在宝可梦双打中做出稳定高胜率决策。`,
        personality: style,
        speaking_style: '简洁、战术化、关注场面收益',
        strengths: ['属性克制', '伤害评估', '队伍轮转'],
      },
    })).data;
  }

  async function prepareTrainingBattle() {
    setBusy(true);
    setError(null);
    try {
      const localFormat = selectedFormatInfo;
      if (localFormat && !localFormat.template_format) {
        throw new Error(`${localFormat.name_zh || localFormat.name} 暂无本地队伍模板，可先用于 Showdown 会话或选择 VGC 2024。`);
      }
      addMessage('初始化本地宝可梦数据');
      await pokemonApi.init();
      const model = await getOrCreateModel();
      const redAgent = await getOrCreateAgent(RED_AGENT, model.id, '稳健进攻');
      const blueAgent = await getOrCreateAgent(BLUE_AGENT, model.id, '平衡反制');

      addMessage(`自动构建双方模板队伍：${localFormat?.name || selectedFormat}`);
      const [redTeam, blueTeam] = await Promise.all([
        pokemonApi.buildTeam(redAgent.id, localFormat?.id || selectedFormat),
        pokemonApi.buildTeam(blueAgent.id, localFormat?.id || selectedFormat),
      ]);

      addMessage(`创建本地对战：${localFormat?.name || selectedFormat}`);
      const battle = (await pokemonApi.createBattle({
        player1_team_id: redTeam.data.id,
        player2_team_id: blueTeam.data.id,
        battle_format: localFormat?.id || selectedFormat,
      })).data;

      const state = battle.summary?.state || (await pokemonApi.getBattleState(battle.id)).data;
      setSetup({ model, redAgent, blueAgent, redTeam: redTeam.data, blueTeam: blueTeam.data });
      setBattleId(battle.id);
      setBattleState(state);
      setAnalysis(null);
      addMessage(`对战已创建：${battle.id}`);
      await refreshOverview();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '准备训练对战失败');
    } finally {
      setBusy(false);
    }
  }

  async function advanceTurn() {
    if (!battleId || !battleState) return;
    setBusy(true);
    setError(null);
    try {
      const player1Active = battleState.player1?.active || [];
      const player2Active = battleState.player2?.active || [];
      const payload = {
        player1_actions: buildActions(player1Active, 2, player2Active),
        player2_actions: buildActions(player2Active, 1, player1Active),
      };

      const result = (await pokemonApi.submitTurn(battleId, payload)).data;
      setBattleState(result);
      addMessage(`Turn ${result.turn} resolved`);
      if (Array.isArray(result.battle_log)) {
        result.battle_log.slice(-4).reverse().forEach((entry: any) => addMessage(formatLogEntry(entry)));
      }
      const summary = (await pokemonApi.analyzeBattle(battleId)).data;
      setAnalysis(summary);
      await refreshOverview();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '推进回合失败');
    } finally {
      setBusy(false);
    }
  }

  async function runKnowledgeSearch() {
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.knowledgeSearch('species_usage', knowledgeQuery, 3)).data;
      setKnowledge(result);
      addMessage(`知识检索完成：${knowledgeQuery}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '知识检索失败');
    } finally {
      setBusy(false);
    }
  }

  async function researchShowdownTeam() {
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(false);
      if (!session.team_species?.length) {
        throw new Error('当前 Showdown 会话没有可研究的队伍成员。');
      }
      const result = (await pokemonApi.researchShowdownSessionTeam(session.session_id, 3)).data;
      const context = result.knowledge_context || {};
      applyShowdownSession(result.session || session);
      setShowdownTeamKnowledge(context.members || []);
      setShowdownTeamKnowledgeSummary(context);
      addMessage(`整队知识检索完成：${context.member_count || 0} members / ${context.result_count || 0} refs`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '整队知识检索失败');
    } finally {
      setBusy(false);
    }
  }

  async function planShowdownChoice() {
    if (!showdownPayload.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.planShowdownDecision({
        payload: showdownPayload,
        mode: showdownMode,
        active_pokemon: selectedFormatInfo?.active_pokemon,
        knowledge_context: showdownSession?.knowledge_context || showdownTeamKnowledgeSummary || undefined,
        learning_profile: activeShowdownLearning || undefined,
        team_context: showdownSession?.team_preview || undefined,
      })).data;
      setShowdownPlan(result.plan);
      addMessage(`Showdown choice: ${result.plan?.command || result.plan?.decision_type || 'none'}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '生成 Showdown 选择失败');
    } finally {
      setBusy(false);
    }
  }

  async function ensureShowdownSession(autoSearch = false) {
    if (showdownSession?.session_id) return showdownSession;
    const session = (await pokemonApi.createShowdownSession({
      username: showdownUsername || 'PokemonBot',
      battle_format: selectedFormatInfo?.id || selectedFormat,
      mode: showdownMode,
      auto_login: showdownAutoLogin,
      auto_accept_challenges: showdownAutoAccept,
      auto_research_team: showdownAutoResearch,
      login_password: showdownPassword || undefined,
      auto_search: autoSearch,
    })).data;
    applyShowdownSession(session);
    setShowdownAnalysis(session.analysis || null);
    if (session.knowledge_context?.members?.length) {
      setShowdownTeamKnowledge(session.knowledge_context.members);
      setShowdownTeamKnowledgeSummary(session.knowledge_context);
    }
    addMessage(`Showdown session ready: ${session.showdown_format}`);
    return session;
  }

  async function createShowdownSession(autoSearch = false) {
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(autoSearch);
      applyShowdownSession(session);
      addMessage(autoSearch ? 'Showdown session created with ladder search queued.' : 'Showdown session created.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '创建 Showdown 会话失败');
    } finally {
      setBusy(false);
    }
  }

  function buildShowdownMissionPayload(overrides: Record<string, unknown> = {}) {
    return {
      username: showdownUsername || 'PokemonBot',
      battle_format: selectedFormatInfo?.id || selectedFormat,
      mode: showdownMode,
      auto_login: showdownAutoLogin,
      auto_accept_challenges: showdownAutoAccept,
      auto_research_team: showdownAutoResearch,
      login_password: showdownPassword || undefined,
      mission_goal: showdownMissionGoal,
      auto_search: showdownMissionGoal !== 'prepare',
      max_actions: Math.min(20, Math.max(1, showdownRunLimit)),
      max_messages: showdownRunLimit,
      stop_on_finished: false,
      ...overrides,
    };
  }

  function parseShowdownProgramFormats() {
    return showdownProgramFormats
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 4);
  }

  function buildShowdownProgramPayload(overrides: Record<string, unknown> = {}) {
    const formats = parseShowdownProgramFormats();
    return buildShowdownMissionPayload({
      formats: formats.length ? formats : undefined,
      format_limit: Math.max(1, Math.min(4, formats.length || 4)),
      rounds: Math.min(10, Math.max(1, showdownChainRounds)),
      chain_limit: Math.min(6, Math.max(1, showdownLoopChains)),
      ...overrides,
    });
  }

  async function previewShowdownMissionPlan() {
    setBusy(true);
    setError(null);
    try {
      const payload = buildShowdownMissionPayload({ login_password: undefined });
      const plan = (await pokemonApi.planShowdownMission(payload)).data;
      setShowdownMissionPlan(plan);
      setShowdownLearning(plan.learning_profile || showdownLearning);
      addMessage(`Mission plan ${plan.mission_goal}: ${plan.mission_goal_source || 'preset'} · ${(plan.executable_plan_actions || plan.allowed_actions || []).length} executable action(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '生成 Showdown 任务计划失败');
    } finally {
      setBusy(false);
    }
  }

  async function previewShowdownTacticalBriefing() {
    setBusy(true);
    setError(null);
    try {
      const briefing = (await pokemonApi.getShowdownTacticalBriefing(
        showdownUsername || 'PokemonBot',
        selectedFormatInfo?.id || selectedFormat,
        showdownMode,
        showdownAutoResearch,
        3
      )).data;
      setShowdownTacticalBriefing(briefing);
      setShowdownLearning(briefing.learning_profile || showdownLearning);
      if (briefing.knowledge_context?.members?.length) {
        setShowdownTeamKnowledge(briefing.knowledge_context.members);
        setShowdownTeamKnowledgeSummary(briefing.knowledge_context);
      }
      addMessage(`Tactical briefing ${briefing.mode}: ${briefing.mission_recommendation?.mission_goal || 'ready'} · ${briefing.tactical_plan?.confidence || 'low'} confidence.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '生成 Showdown 战术简报失败');
    } finally {
      setBusy(false);
    }
  }

  async function startShowdownMission(plannedRequest?: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      resetShowdownState();
      const response = (await pokemonApi.startShowdownMission(buildShowdownMissionPayload(plannedRequest || {}))).data;
      const session = response.session || response.supervisor?.session;
      applyShowdownSession(session);
      setShowdownAnalysis(response.supervisor?.analysis || session?.analysis || null);
      setShowdownLearning(response.supervisor?.learning_profile || session?.learning_profile || null);
      if (session?.knowledge_context?.members?.length) {
        setShowdownTeamKnowledge(session.knowledge_context.members);
        setShowdownTeamKnowledgeSummary(session.knowledge_context);
      }
      const lastStep = [...(response.supervisor?.steps || [])].reverse().find((step: any) => step.result?.decision);
      setShowdownPlan(lastStep?.result?.decision || null);
      addMessage(`Mission ${response.mission_summary?.mission_goal || showdownMissionGoal}: ${response.mission_summary?.stop_reason || 'ready'} · ${response.mission_summary?.step_count || 0} action(s).`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '启动 Showdown 自主任务失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownTrainingChain(plannedRequest?: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      resetShowdownState();
      const response = (await pokemonApi.runShowdownTrainingChain(buildShowdownMissionPayload(plannedRequest || {
        rounds: Math.min(10, Math.max(1, showdownChainRounds)),
      }))).data;
      setShowdownTrainingChain(response);
      applyShowdownSession(response.final_session);
      setShowdownLearning(response.learning_profile || response.final_session?.learning_profile || null);
      setShowdownAnalysis(response.final_session?.analysis || null);
      const lastRound = [...(response.rounds || [])].reverse()[0];
      const recoverySummary = response.recovery?.status
        ? ` · recovery ${response.recovery.status}${response.recovery.actions?.length ? `/${response.recovery.actions.length}` : ''}`
        : '';
      const resumedSummary = response.initial_recovery?.actions?.length ? ' · resumed history' : '';
      const nextSummary = response.next_training_chain?.intervention ? ` · next ${response.next_training_chain.intervention}` : '';
      addMessage(`Training chain ${response.completed_rounds}/${response.requested_rounds}: ${response.stop_reason} · ${lastRound?.planned_goal || 'auto'}${recoverySummary}${resumedSummary}${nextSummary}.`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '启动 Showdown 训练链失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownTrainingLoop() {
    setBusy(true);
    setError(null);
    try {
      resetShowdownState();
      const response = (await pokemonApi.runShowdownTrainingLoop(buildShowdownMissionPayload({
        rounds: Math.min(10, Math.max(1, showdownChainRounds)),
        chain_limit: Math.min(6, Math.max(1, showdownLoopChains)),
      }))).data;
      const lastChain = [...(response.chains || [])].reverse()[0];
      setShowdownTrainingLoop(response);
      setShowdownTrainingChain(lastChain || null);
      applyShowdownSession(response.final_session || lastChain?.final_session);
      setShowdownLearning(response.final_session?.learning_profile || lastChain?.final_session?.learning_profile || null);
      setShowdownAnalysis(response.final_session?.analysis || lastChain?.final_session?.analysis || null);
      addMessage(`Training loop ${response.completed_chains}/${response.requested_chain_limit}: ${response.stop_reason} · ${response.total_completed_rounds || 0} round(s).`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '启动 Showdown 训练循环失败');
    } finally {
      setBusy(false);
    }
  }

  async function previewShowdownTrainingProgram() {
    setBusy(true);
    setError(null);
    try {
      const plan = (await pokemonApi.planShowdownTrainingProgram(buildShowdownProgramPayload({
        login_password: undefined,
      }))).data;
      setShowdownTrainingProgramPlan(plan);
      addMessage(`Training program plan ${plan.planned_format_count}/${plan.requested_format_limit}: ${plan.status} · ${plan.total_existing_samples || 0} sample(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '预览 Showdown 多格式训练失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownTrainingProgram(plannedRequest?: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      resetShowdownState();
      const response = (await pokemonApi.runShowdownTrainingProgram(buildShowdownProgramPayload(plannedRequest || {}))).data;
      const lastFormat = [...(response.formats || [])].reverse()[0];
      const lastLoop = lastFormat?.loop || null;
      const lastChain = [...(lastLoop?.chains || [])].reverse()[0];
      setShowdownTrainingProgram(response);
      setShowdownTrainingLoop(lastLoop);
      setShowdownTrainingChain(lastChain || null);
      applyShowdownSession(lastLoop?.final_session || lastChain?.final_session);
      setShowdownLearning(lastLoop?.final_session?.learning_profile || lastChain?.final_session?.learning_profile || null);
      setShowdownAnalysis(lastLoop?.final_session?.analysis || lastChain?.final_session?.analysis || null);
      addMessage(`Training program ${response.completed_formats}/${response.requested_format_limit}: ${response.stop_reason} · ${response.total_completed_rounds || 0} round(s).`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '启动 Showdown 多格式训练失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownTrainingProgramPipeline(plannedRequest?: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      resetShowdownState();
      const response = (await pokemonApi.runShowdownTrainingProgramPipeline(buildShowdownProgramPayload({
        ...(plannedRequest || {}),
        stage_limit: 3,
      }))).data;
      const finalProgram = response.final_result || null;
      const lastFormat = [...(finalProgram?.formats || [])].reverse()[0];
      const lastLoop = lastFormat?.loop || null;
      const lastChain = [...(lastLoop?.chains || [])].reverse()[0];
      setShowdownTrainingProgramPipeline(response);
      setShowdownTrainingProgram(finalProgram);
      setShowdownTrainingLoop(lastLoop);
      setShowdownTrainingChain(lastChain || null);
      applyShowdownSession(lastLoop?.final_session || lastChain?.final_session);
      setShowdownLearning(lastLoop?.final_session?.learning_profile || lastChain?.final_session?.learning_profile || null);
      setShowdownAnalysis(lastLoop?.final_session?.analysis || lastChain?.final_session?.analysis || null);
      addMessage(`Training pipeline ${response.completed_stages}/${response.requested_stage_limit}: ${response.pipeline_health?.status || response.stop_reason}.`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '启动 Showdown 多格式流水线失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownTrainingProgramAutopilot(plannedRequest?: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      resetShowdownState();
      const response = (await pokemonApi.runShowdownTrainingProgramAutopilot(buildShowdownProgramPayload({
        ...(plannedRequest || {}),
        stage_limit: 3,
        cycle_limit: 2,
      }))).data;
      const finalPipeline = response.final_result || null;
      const finalProgram = finalPipeline?.final_result || null;
      const lastFormat = [...(finalProgram?.formats || [])].reverse()[0];
      const lastLoop = lastFormat?.loop || null;
      const lastChain = [...(lastLoop?.chains || [])].reverse()[0];
      setShowdownTrainingProgramAutopilot(response);
      setShowdownTrainingProgramPipeline(finalPipeline);
      setShowdownTrainingProgram(finalProgram);
      setShowdownTrainingLoop(lastLoop);
      setShowdownTrainingChain(lastChain || null);
      applyShowdownSession(lastLoop?.final_session || lastChain?.final_session);
      setShowdownLearning(lastLoop?.final_session?.learning_profile || lastChain?.final_session?.learning_profile || null);
      setShowdownAnalysis(lastLoop?.final_session?.analysis || lastChain?.final_session?.analysis || null);
      addMessage(`Training autopilot ${response.completed_cycles}/${response.requested_cycle_limit}: ${response.autopilot_health?.status || response.stop_reason}.`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '启动 Showdown 训练自动驾驶失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownSessionStep() {
    if (!showdownPayload.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(false);
      const result = (await pokemonApi.processShowdownSessionMessage(session.session_id, {
        payload: showdownPayload,
        auto_respond: true,
      })).data;
      const nextAnalysis = result.session?.analysis || (await pokemonApi.analyzeShowdownSession(session.session_id)).data;
      applyShowdownSession(result.session);
      setShowdownAnalysis(nextAnalysis);
      setShowdownLearning(result.learning_profile || showdownLearning);
      setShowdownPlan(result.decision || showdownPlan);
      addMessage(`Showdown session ${result.session?.status || 'ready'}: ${(result.commands || []).join(' / ') || 'no command'}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '推进 Showdown 会话失败');
    } finally {
      setBusy(false);
    }
  }

  async function startShowdownSearch() {
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(false);
      const result = (await pokemonApi.startShowdownSearch(session.session_id)).data;
      applyShowdownSession(result.session);
      addMessage(`Search queued: ${(result.commands || []).join(' / ')}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '生成搜索命令失败');
    } finally {
      setBusy(false);
    }
  }

  async function cancelShowdownSearch() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.cancelShowdownSearch(showdownSession.session_id)).data;
      applyShowdownSession(result.session);
      addMessage(`Cancel search queued: ${(result.commands || []).join(' / ')}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '取消搜索失败');
    } finally {
      setBusy(false);
    }
  }

  async function acceptShowdownChallenge() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.acceptShowdownChallenge(showdownSession.session_id, showdownChallengeUser)).data;
      applyShowdownSession(result.session);
      addMessage(`Challenge accepted: ${(result.commands || []).join(' / ')}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '接受挑战失败');
    } finally {
      setBusy(false);
    }
  }

  async function rejectShowdownChallenge() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.rejectShowdownChallenge(showdownSession.session_id, showdownChallengeUser)).data;
      applyShowdownSession(result.session);
      addMessage(`Challenge rejected: ${(result.commands || []).join(' / ')}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '拒绝挑战失败');
    } finally {
      setBusy(false);
    }
  }

  async function connectShowdownSession() {
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(false);
      const result = (await pokemonApi.connectShowdownSession(session.session_id, true)).data;
      applyShowdownSession(result.session);
      addMessage(`Connected to Showdown, sent ${result.sent?.length || 0} pending command(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '连接 Showdown websocket 失败');
    } finally {
      setBusy(false);
    }
  }

  async function flushShowdownPending() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.flushShowdownSession(showdownSession.session_id)).data;
      applyShowdownSession(result.session);
      addMessage(`Sent pending: ${result.sent?.length || 0} command(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '发送待发命令失败');
    } finally {
      setBusy(false);
    }
  }

  async function runLiveShowdownOnce() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.runShowdownSessionOnce(showdownSession.session_id, {
        auto_respond: true,
        send_commands: true,
      })).data;
      applyShowdownSession(result.session);
      setShowdownAnalysis(result.session?.analysis || showdownAnalysis);
      setShowdownLearning(result.learning_profile || showdownLearning);
      setShowdownPlan(result.decision || showdownPlan);
      addMessage(`Live step ${result.session?.status || 'ready'}: ${result.sent?.length || 0} sent.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '执行 Showdown 单步失败');
    } finally {
      setBusy(false);
    }
  }

  async function runLiveShowdownUntil() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.runShowdownSessionUntil(showdownSession.session_id, {
        auto_respond: true,
        send_commands: true,
        max_messages: showdownRunLimit,
        stop_on_finished: true,
      })).data;
      applyShowdownSession(result.session, result.run_summary);
      setShowdownAnalysis(result.session?.analysis || showdownAnalysis);
      setShowdownLearning(result.learning_profile || showdownLearning);
      const steps = result.steps || [];
      const lastDecision = [...steps].reverse().find((step: any) => step.decision)?.decision;
      setShowdownPlan(lastDecision || showdownPlan);
      addMessage(`Auto run stopped at ${result.run_summary?.stopped_reason || result.session?.status || 'ready'} after ${steps.length} message(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '自动运行 Showdown 会话失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownAutopilot() {
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(false);
      const result = (await pokemonApi.autopilotShowdownSession(session.session_id, {
        auto_respond: true,
        send_commands: true,
        auto_search: true,
        require_live_readiness: true,
        max_messages: showdownRunLimit,
        stop_on_finished: true,
      })).data;
      applyShowdownSession(result.session, result.run_summary);
      setShowdownAnalysis(result.session?.analysis || showdownAnalysis);
      setShowdownLearning(result.learning_profile || showdownLearning);
      const steps = result.steps || [];
      const lastDecision = [...steps].reverse().find((step: any) => step.decision)?.decision;
      setShowdownPlan(lastDecision || showdownPlan);
      addMessage(`Autopilot ${result.run_summary?.stopped_reason || result.session?.status || 'ready'}: ${(result.actions || []).join(' / ') || 'running'} · ${steps.length} message(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Showdown 自动驾驶失败');
    } finally {
      setBusy(false);
    }
  }

  async function closeShowdownSession() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const session = (await pokemonApi.closeShowdownSession(showdownSession.session_id)).data;
      applyShowdownSession(session);
      addMessage('Showdown websocket closed.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '关闭 Showdown 会话失败');
    } finally {
      setBusy(false);
    }
  }

  async function refreshShowdownReadiness() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const readiness = (await pokemonApi.getShowdownSessionReadiness(showdownSession.session_id)).data;
      setShowdownSession((current: any) => current ? { ...current, live_readiness: readiness.live_readiness, next_actions: readiness.next_actions } : current);
      addMessage(`Live readiness ${readiness.live_readiness?.status || 'unknown'}: ${readiness.live_readiness?.score ?? 0}/100.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '检查 Showdown 实战就绪失败');
    } finally {
      setBusy(false);
    }
  }

  async function refreshShowdownMatchupBriefing() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const activeRoom = showdownRooms.find((room) => room.preview || room.battlefield) || showdownRooms[0];
      const briefing = (await pokemonApi.getShowdownSessionMatchupBriefing(
        showdownSession.session_id,
        activeRoom?.room_id,
        showdownAutoResearch,
        3
      )).data;
      setShowdownMatchupBriefing(briefing);
      if (briefing.knowledge_context?.members?.length) {
        setShowdownTeamKnowledge(briefing.knowledge_context.members);
        setShowdownTeamKnowledgeSummary(briefing.knowledge_context);
      }
      addMessage(`Matchup briefing: ${(briefing.opponent?.species || []).slice(0, 3).join(' / ') || 'waiting'} · ${briefing.matchup_plan?.confidence || 'low'} confidence.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '生成 Showdown 对局简报失败');
    } finally {
      setBusy(false);
    }
  }

  async function executeShowdownNextAction(actionName: string) {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const response = (await pokemonApi.executeShowdownNextAction(showdownSession.session_id, {
        action: actionName,
        max_messages: showdownRunLimit,
        auto_search: true,
        send_commands: true,
        require_live_readiness: true,
        stop_on_finished: true,
      })).data;
      const result = response.result || {};
      applyShowdownSession(response.session || result.session, result.run_summary);
      setShowdownAnalysis(response.analysis || response.session?.analysis || showdownAnalysis);
      setShowdownLearning(response.learning_profile || showdownLearning);
      if (response.knowledge_context?.members?.length) {
        setShowdownTeamKnowledge(response.knowledge_context.members);
        setShowdownTeamKnowledgeSummary(response.knowledge_context);
      }
      const steps = result.steps || [];
      const lastDecision = [...steps].reverse().find((step: any) => step.decision)?.decision;
      setShowdownPlan(lastDecision || result.decision || showdownPlan);
      addMessage(`Next action ${response.action || actionName}: ${result.run_summary?.stopped_reason || response.session?.status || 'done'}`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '执行 Showdown 建议动作失败');
    } finally {
      setBusy(false);
    }
  }

  async function runShowdownSupervisor() {
    if (!showdownSession?.session_id) return;
    setBusy(true);
    setError(null);
    try {
      const response = (await pokemonApi.superviseShowdownSession(showdownSession.session_id, {
        max_actions: Math.min(20, Math.max(1, showdownRunLimit)),
        max_messages: showdownRunLimit,
        auto_search: true,
        send_commands: true,
        require_live_readiness: true,
        stop_on_finished: false,
        stop_on_error: true,
      })).data;
      applyShowdownSession(response.session);
      setShowdownAnalysis(response.analysis || response.session?.analysis || showdownAnalysis);
      setShowdownLearning(response.learning_profile || showdownLearning);
      if (response.knowledge_context?.members?.length) {
        setShowdownTeamKnowledge(response.knowledge_context.members);
        setShowdownTeamKnowledgeSummary(response.knowledge_context);
      }
      const lastStep = [...(response.steps || [])].reverse().find((step: any) => step.result?.decision);
      setShowdownPlan(lastStep?.result?.decision || showdownPlan);
      addMessage(`Supervisor stopped: ${response.stop_reason || 'done'} · ${response.step_count || 0} action(s).`);
      refreshShowdownMastery();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Showdown 监督循环失败');
    } finally {
      setBusy(false);
    }
  }

  const phaseItems = [
    ['Phase 1', '本地双打引擎、伤害计算、REST 流程、训练 UI'],
    ['Phase 2', '知识检索、缓存、决策记录、强化学习雏形'],
    ['Phase 3', '等级驱动队伍构建、对战分析、经验进化'],
    ['Phase 4', '多格式目录、Showdown 队伍上传、会话运行器和自动选择命令'],
    ['Phase 5', '按格式选择目标策略，单打省略 target，双打保留精确目标'],
    ['Phase 6', '自动接受同格式挑战，并在建队后自动研究整队知识'],
    ['Phase 7', '学习档案输出训练重点，将真实结果反哺下一局策略'],
    ['Phase 8', '同步真实房间元数据，跟踪对手、规则、分级和结果'],
    ['Phase 9', '一键自动驾驶：连接、搜索、收发消息和自动决策'],
    ['Phase 10', '学习档案反哺自动建队，低收益时自动保守化调整'],
    ['Phase 11', '学习档案反哺自动出招评分，弱势时偏向安全决策'],
    ['Phase 12', '战后学习档案即时回写会话，下一步策略直接使用新样本'],
    ['Phase 13', '队伍预览战略首发评分，按角色、知识和学习档案排序'],
    ['Phase 14', '同步战场在场与 HP，双打目标优先锁定低血量对手'],
    ['Phase 15', '同步双方 poke 预览，对手阵容反哺首发评分'],
    ['Phase 16', '强制换人按 HP、角色和对手预览评分后排'],
    ['Phase 17', '无可用招式且未被 trapped 时自动评分换人'],
    ['Phase 18', '按 room/rqid 去重，避免重复 websocket 请求重复出招'],
    ['Phase 19', '自动驾驶接收失败时记录错误并返回可见步骤'],
    ['Phase 20', '连续运行返回结构化摘要，前端展示停止原因、发送量和最后决策'],
    ['Phase 21', '会话快照保存最近运行历史，刷新后仍能复盘自动驾驶结果'],
    ['Phase 22', '真实 Showdown 连接、发送、接收和登录 assertion 阶段诊断'],
    ['Phase 23', '会话快照给出自动驾驶恢复计划和下一步动作建议'],
    ['Phase 24', '前端可一键执行恢复计划，建议动作直接驱动 Showdown 控制台'],
    ['Phase 25', '后端统一执行恢复动作，智能体可通过 API 自主推进会话'],
    ['Phase 26', '后端监督循环可连续执行推荐动作，推进会话直到停止条件'],
    ['Phase 27', '会话快照保存监督循环历史，前端展示自主执行轨迹'],
    ['Phase 28', '自主任务入口可一键创建队伍、启动会话并进入监督循环'],
    ['Phase 29', 'Showdown 学习档案生成 Mastery 排行并在控制台展示实力变化'],
    ['Phase 30', '自主任务支持 prepare/queue/ladder/learn 目标预设和动作边界'],
    ['Phase 31', '会话快照保存自主任务历史，前端展示任务目标和动作边界'],
    ['Phase 32', '自主任务支持 auto 目标，根据学习档案和知识状态选择训练节奏'],
    ['Phase 33', '学习档案输出结构化训练计划，任务摘要展示下一轮目标和动作队列'],
    ['Phase 34', 'auto 自主任务读取训练计划推荐下一轮目标，并展示推荐来源'],
    ['Phase 35', '训练计划动作会翻译为可执行 supervisor 白名单，任务摘要展示执行覆盖'],
    ['Phase 36', '新增下一轮任务计划预览接口，前端可查看并按计划启动自主训练'],
    ['Phase 37', '新增多轮训练链入口，按学习计划连续规划、执行、评分并在前端复盘'],
    ['Phase 38', '会话快照保存训练链历史，刷新后仍能复盘多轮训练表现'],
    ['Phase 39', '训练链输出 Mastery 前后变化、样本增量和趋势建议，判断是否真的变强'],
    ['Phase 40', '会话快照汇总训练链长期趋势，展示持续进步、下降和样本积累情况'],
    ['Phase 41', '实战就绪审计检查登录、队伍、知识、连接、待发命令和天梯路径'],
    ['Phase 42', '多格式能力矩阵展示每个 Showdown 格式的队伍、策略、学习和自动化覆盖'],
    ['Phase 43', '战术简报整合格式、队伍、学习档案和知识检索，给出下一局开局计划'],
    ['Phase 44', '对手预览 Matchup 简报识别威胁、目标优先级、首发调整和风险控制'],
    ['Phase 45', 'Matchup 信号反哺自动决策，出招候选展示 matchup_used 证据'],
    ['Phase 46', '自动选择输出决策安全审计，标记可发送状态、风险检查和兜底选择'],
    ['Phase 47', '自动驾驶执行前应用决策审计门控，阻断 blocked 命令并在运行摘要中展示原因'],
    ['Phase 48', '一键自动驾驶启用实战就绪 gate，未通过登录、队伍、连接等检查时停止发送'],
    ['Phase 49', '多格式策略画像反哺首发、换人和出招评分，区分双打、单打 OU 与随机战'],
    ['Phase 50', '自动建队输出格式角色覆盖审计，暴露队伍分数、策略缺口和学习调整证据'],
    ['Phase 51', 'auto 自主任务读取建队审计，低分、blocked 或角色缺口时优先研究队伍'],
    ['Phase 52', 'auto 自主任务读取实战就绪审计，blocked 时先复核 readiness 再发送命令'],
    ['Phase 53', '学习档案沉淀 battle lessons 和可执行 training tasks，实战后能复用经验调整下一轮任务'],
    ['Phase 54', 'auto 自主任务优先读取 training tasks，按任务证据驱动 supervisor 动作白名单'],
    ['Phase 55', 'mission summary 回写 training task progress，显示 completed/partial/pending/unsupported 执行证据'],
    ['Phase 56', 'training-chain 汇总 recovery actions，把未完成训练任务转成下一轮恢复队列'],
    ['Phase 57', 'training-chain 后续轮次自动消费上一轮 recovery actions，形成自我修复训练闭环'],
    ['Phase 58', '新 training-chain 会继承同训练师/格式的历史 recovery actions，支持跨链续跑'],
    ['Phase 59', '学习档案输出长期 policy evaluation，在探索、稳定和利用之间自动切换策略'],
    ['Phase 60', '自主任务读取 policy evaluation，按收集、稳定、探索和利用阶段规划目标与动作边界'],
    ['Phase 61', '自主任务回写 policy action progress，并将未完成策略动作纳入训练链恢复队列'],
    ['Phase 62', '训练链追踪 recovery burn-down，判断恢复动作是否清除、卡住或产生新队列'],
    ['Phase 63', 'stuck recovery 会自动扩展下一轮动作边界，避免训练链反复卡在同一恢复队列'],
    ['Phase 64', '训练链输出 health/intervention 摘要，驱动继续训练、恢复扩展或补样本'],
    ['Phase 65', '训练链把 health/intervention 转成下一轮可执行 preset，前端可一键继续训练'],
    ['Phase 66', '训练循环自动消费 next_training_chain preset，按上限连续续跑直到阻断或达成上限'],
    ['Phase 67', '多格式训练计划按 curriculum 轮转多个 Showdown 格式，汇总 program health 并生成下一轮 preset'],
    ['Phase 68', '多格式训练支持 plan 预览和 program preset 续跑，执行前能审查 curriculum、样本和格式优先级'],
    ['Phase 69', '多格式 program plan 注入首轮 mission preview，执行前展示 readiness、team audit 和可执行动作风险'],
    ['Phase 70', '多格式训练执行前应用 preflight gate，blocked 格式会跳过并进入 program health 人工审查'],
    ['Phase 71', 'preflight blocked 时生成 recovery program preset，先恢复 readiness/team audit 再继续多格式训练'],
    ['Phase 72', 'recovery preset 同时生成恢复后续跑请求，blocked 格式修复后可回到原多格式 curriculum'],
    ['Phase 73', '多格式训练 pipeline 自动串联 program、recovery 和恢复后续跑阶段，减少人工连续点击'],
    ['Phase 74', 'pipeline 输出 autonomous trace 和 next action，让无人值守训练调度器能直接判断继续、恢复或人工审查'],
    ['Phase 75', 'training autopilot 循环消费 pipeline next action，在 cycle 预算内自动续跑多格式训练'],
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border bg-surface-raised/80 p-5 shadow-lg shadow-black/20">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-medium text-accent-hover">Pokemon Showdown Agent Lab</p>
            <h1 className="mt-2 text-3xl font-semibold text-white">宝可梦智能体训练台</h1>
            <p className="mt-3 text-sm leading-6 text-gray-400">
              从本地 VGC 双打模拟开始，让智能体自动建队、执行回合、记录对战日志，并逐步接入知识库、学习机制和 Pokemon Showdown 实战。
            </p>
          </div>
          <div className="flex w-full flex-col gap-3 lg:w-auto lg:min-w-80">
            <label className="text-xs uppercase text-gray-500">
              Format
              <select
                value={selectedFormat}
                onChange={(event) => {
                  setSelectedFormat(event.target.value);
                  resetShowdownState();
                }}
                className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm normal-case text-gray-100 outline-none focus:border-accent"
              >
                {formats.length ? formats.map((format) => (
                  <option key={format.id} value={format.id}>
                    {format.name_zh || format.name}
                  </option>
                )) : (
                  <option value="vgc2024">VGC 2024</option>
                )}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={prepareTrainingBattle}
                disabled={busy || Boolean(selectedFormatInfo && !selectedFormatInfo.template_format)}
                className="btn-primary inline-flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v6h6M20 20v-6h-6M20 9A8 8 0 006.7 5.1L4 10M4 15a8 8 0 0013.3 3.9L20 14" />
                </svg>
                准备训练环境
              </button>
              <button onClick={refreshOverview} disabled={busy} className="btn-secondary disabled:opacity-50">
                刷新状态
              </button>
            </div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-5">
          <Metric label="Species" value={speciesCount} />
          <Metric label="Moves" value={moveCount} />
          <Metric label="Battles" value={history.length} />
          <Metric label="Format" value={selectedFormatInfo?.showdown_format || selectedFormat} />
          <Metric label="WebSocket" value={battleId ? 'ready' : 'idle'} />
        </div>
        {selectedFormatInfo && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
            <span className="rounded border border-border bg-black/20 px-2 py-1">{selectedFormatInfo.battle_type}</span>
            <span className="rounded border border-border bg-black/20 px-2 py-1">team {selectedFormatInfo.team_size}</span>
            <span className="rounded border border-border bg-black/20 px-2 py-1">active {selectedFormatInfo.active_pokemon}</span>
            {!selectedFormatInfo.template_format && (
              <span className="rounded border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-amber-200">Showdown only</span>
            )}
          </div>
        )}
        {formatCapabilities ? (
          <div className="mt-3 rounded-md border border-border bg-black/20 p-3 text-xs text-gray-300">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-[10px] font-semibold uppercase text-gray-500">Format coverage</span>
              <span className="rounded bg-black/30 px-2 py-0.5 text-[10px] text-gray-100">
                {formatCapabilities.ready_count || 0}/{formatCapabilities.format_count || 0} ready · {formatCapabilities.coverage_score || 0}%
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {(formatCapabilities.formats || []).map((item: any) => {
                const active = item.format?.id === selectedFormat;
                return (
                  <button
                    key={item.format?.id}
                    onClick={() => {
                      setSelectedFormat(item.format.id);
                      resetShowdownState();
                    }}
                    className={`rounded border px-2 py-2 text-left transition ${
                      active ? 'border-accent bg-accent/10 text-white' : 'border-border bg-black/20 text-gray-400 hover:text-white'
                    }`}
                  >
                    <div className="truncate text-[11px] font-semibold">{item.format?.name_zh || item.format?.name}</div>
                    <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                      <span>{item.automation_readiness}</span>
                      <span>{item.battle_policy?.target_policy}</span>
                    </div>
                  </button>
                );
              })}
            </div>
            {activeFormatCapability ? (
              <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
                <Metric label="Team Source" value={activeFormatCapability.team?.source || '-'} compact />
                <Metric label="Autopilot" value={activeFormatCapability.battle_policy?.supports_autopilot ? 'yes' : 'no'} compact />
                <Metric label="Samples" value={activeFormatCapability.learning?.battles || 0} compact />
                <Metric label="Next" value={activeFormatCapability.learning?.next_mission_goal || '-'} compact />
                <Metric label="Style" value={activeFormatCapability.strategy_profile?.archetype || activeFormatCapability.battle_policy?.archetype || '-'} compact />
                <Metric label="Priorities" value={(activeFormatCapability.strategy_profile?.priorities || []).length} compact />
                <Metric label="Team Score" value={activeFormatCapability.team?.audit?.score ?? '-'} compact />
                <Metric label="Audit" value={activeFormatCapability.team?.audit?.status || '-'} compact />
              </div>
            ) : null}
            {activeFormatCapability?.strategy_profile?.priorities?.length ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {activeFormatCapability.strategy_profile.priorities.slice(0, 6).map((priority: string) => (
                  <span key={`format-priority-${priority}`} className="rounded border border-border bg-black/20 px-1.5 py-0.5 text-[10px] text-gray-300">
                    {priority}
                  </span>
                ))}
              </div>
            ) : null}
            {activeFormatCapability?.strategy_profile?.opening_style ? (
              <div className="mt-2 break-words rounded border border-border bg-black/20 p-2 text-[10px] leading-4 text-gray-400">
                {activeFormatCapability.strategy_profile.opening_style}
              </div>
            ) : null}
            {activeFormatCapability?.team?.audit?.gaps?.length ? (
              <div className="mt-2 rounded border border-amber-500/30 bg-amber-500/10 p-2">
                <div className="text-[10px] font-semibold uppercase text-amber-200">Team gaps</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {activeFormatCapability.team.audit.gaps.slice(0, 5).map((gap: string) => (
                    <span key={`format-team-gap-${gap}`} className="rounded bg-black/30 px-1.5 py-0.5 text-[10px] text-amber-100">
                      {gap}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      {error && (
        <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <BattleField state={battleState} />
          {battleState && !battleState.winner && (
            <MoveSelector
              activePokemon={battleState.player1?.active || []}
              bench={battleState.player1?.bench || []}
              busy={busy}
              onAutoTurn={advanceTurn}
            />
          )}
          <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <TeamManager label="Player 1" agent={setup.redAgent} team={setup.redTeam} tone="blue" />
            <TeamManager label="Player 2" agent={setup.blueAgent} team={setup.blueTeam} tone="red" />
          </section>
        </div>

        <aside className="space-y-4">
          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">运行日志</h2>
            <div className="mt-3 max-h-72 space-y-2 overflow-y-auto">
              {messages.length ? messages.map((message, index) => (
                <div key={`${message}-${index}`} className="rounded-md border border-border bg-black/20 px-3 py-2 text-sm text-gray-300">
                  {message}
                </div>
              )) : (
                <p className="rounded-md border border-dashed border-border p-4 text-sm text-gray-500">
                  暂无日志，先准备训练环境。
                </p>
              )}
            </div>
          </section>

          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">知识检索</h2>
            <div className="mt-3 flex gap-2">
              <input
                value={knowledgeQuery}
                onChange={(event) => setKnowledgeQuery(event.target.value)}
                className="input-field"
                placeholder="Pokemon name"
              />
              <button onClick={runKnowledgeSearch} disabled={busy || !knowledgeQuery.trim()} className="btn-secondary disabled:opacity-50">
                搜索
              </button>
            </div>
            <div className="mt-3 rounded-md border border-border bg-black/20 p-3 text-sm text-gray-400">
              {knowledge ? (
                <div className="space-y-2">
                  <div>Query: {knowledge.query_key || knowledgeQuery}</div>
                  <div>Results: {knowledge.results?.length || 0}</div>
                  {knowledge.cached !== undefined && <div>Cached: {String(knowledge.cached)}</div>}
                </div>
              ) : (
                '检索排位数据库和外部知识源，结果会进入后端缓存。'
              )}
            </div>
            {showdownTeamKnowledge.length ? (
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between gap-2 text-xs uppercase text-gray-500">
                  <span>Showdown team research</span>
                  {showdownTeamKnowledgeSummary && (
                    <span>
                      {showdownTeamKnowledgeSummary.result_count || 0} refs · {showdownTeamKnowledgeSummary.cached_count || 0} cached
                    </span>
                  )}
                </div>
                {showdownTeamKnowledge.map((item) => {
                  const firstResult = item.results?.[0];
                  return (
                    <div key={item.species} className="rounded-md border border-border bg-black/20 p-3 text-xs text-gray-400">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-gray-100">{item.species}</span>
                        <span>{item.error ? 'error' : `${item.results?.length || 0} refs`}</span>
                      </div>
                      {item.cached !== undefined && <div className="mt-1 text-gray-500">cached: {String(item.cached)}</div>}
                      {item.error ? (
                        <div className="mt-1 text-red-200">{item.error}</div>
                      ) : firstResult ? (
                        <div className="mt-1 truncate text-gray-500">{firstResult.title || firstResult.url}</div>
                      ) : (
                        <div className="mt-1 text-gray-500">no external result</div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </section>

          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">对战分析</h2>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <Metric label="Turns" value={analysis?.turns ?? battleState?.turn ?? 0} compact />
              <Metric label="Damage" value={analysis?.total_damage ?? 0} compact />
              <Metric label="Faints" value={analysis?.faints ?? 0} compact />
              <Metric label="Winner" value={battleState?.winner ?? '-'} compact />
            </div>
          </section>

          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">Phase 进度</h2>
            <div className="mt-3 space-y-2">
              {phaseItems.map(([phase, text]) => (
                <div key={phase} className="rounded-md border border-border bg-black/20 px-3 py-2">
                  <div className="text-sm font-medium text-gray-100">{phase}</div>
                  <div className="mt-1 text-xs leading-5 text-gray-500">{text}</div>
                </div>
              ))}
            </div>
          </section>

          <ShowdownConsole
            showdownUsername={showdownUsername}
            setShowdownUsername={setShowdownUsername}
            showdownPassword={showdownPassword}
            setShowdownPassword={setShowdownPassword}
            showdownAutoLogin={showdownAutoLogin}
            setShowdownAutoLogin={setShowdownAutoLogin}
            showdownAutoAccept={showdownAutoAccept}
            setShowdownAutoAccept={setShowdownAutoAccept}
            showdownAutoResearch={showdownAutoResearch}
            setShowdownAutoResearch={setShowdownAutoResearch}
            showdownRunLimit={showdownRunLimit}
            setShowdownRunLimit={setShowdownRunLimit}
            showdownChainRounds={showdownChainRounds}
            setShowdownChainRounds={setShowdownChainRounds}
            showdownLoopChains={showdownLoopChains}
            setShowdownLoopChains={setShowdownLoopChains}
            showdownProgramFormats={showdownProgramFormats}
            setShowdownProgramFormats={setShowdownProgramFormats}
            showdownMode={showdownMode}
            setShowdownMode={setShowdownMode}
            showdownMissionGoal={showdownMissionGoal}
            setShowdownMissionGoal={setShowdownMissionGoal}
            showdownPayload={showdownPayload}
            setShowdownPayload={setShowdownPayload}
            busy={busy}
            showdownSession={showdownSession}
            showdownPlan={showdownPlan}
            showdownRunSummary={showdownRunSummary}
            showdownMissionPlan={showdownMissionPlan}
            showdownTacticalBriefing={showdownTacticalBriefing}
            showdownMatchupBriefing={showdownMatchupBriefing}
            showdownTrainingChain={activeShowdownTrainingChain}
            showdownTrainingLoop={activeShowdownTrainingLoop}
            showdownTrainingProgramPlan={activeShowdownTrainingProgramPlan}
            showdownTrainingProgram={activeShowdownTrainingProgram}
            showdownTrainingProgramPipeline={activeShowdownTrainingProgramPipeline}
            showdownTrainingProgramAutopilot={activeShowdownTrainingProgramAutopilot}
            showdownMastery={showdownMastery}
            showdownTeamKnowledge={showdownTeamKnowledge}
            showdownTeamKnowledgeSummary={showdownTeamKnowledgeSummary}
            showdownChallengeUser={showdownChallengeUser}
            showdownRooms={showdownRooms}
            activeLiveReadiness={activeLiveReadiness}
            activeShowdownLearning={activeShowdownLearning}
            activeTrainingChainTrend={activeTrainingChainTrend}
            showdownTargetPolicy={showdownTargetPolicy}
            selectedFormat={selectedFormat}
            createShowdownSession={createShowdownSession}
            startShowdownMission={startShowdownMission}
            previewShowdownMissionPlan={previewShowdownMissionPlan}
            previewShowdownTacticalBriefing={previewShowdownTacticalBriefing}
            previewShowdownTrainingProgram={previewShowdownTrainingProgram}
            runShowdownTrainingChain={runShowdownTrainingChain}
            runShowdownTrainingLoop={runShowdownTrainingLoop}
            runShowdownTrainingProgram={runShowdownTrainingProgram}
            runShowdownTrainingProgramPipeline={runShowdownTrainingProgramPipeline}
            runShowdownTrainingProgramAutopilot={runShowdownTrainingProgramAutopilot}
            startShowdownSearch={startShowdownSearch}
            connectShowdownSession={connectShowdownSession}
            refreshShowdownReadiness={refreshShowdownReadiness}
            refreshShowdownMatchupBriefing={refreshShowdownMatchupBriefing}
            runLiveShowdownOnce={runLiveShowdownOnce}
            runLiveShowdownUntil={runLiveShowdownUntil}
            runShowdownAutopilot={runShowdownAutopilot}
            runShowdownSupervisor={runShowdownSupervisor}
            researchShowdownTeam={researchShowdownTeam}
            cancelShowdownSearch={cancelShowdownSearch}
            acceptShowdownChallenge={acceptShowdownChallenge}
            rejectShowdownChallenge={rejectShowdownChallenge}
            flushShowdownPending={flushShowdownPending}
            closeShowdownSession={closeShowdownSession}
            resetShowdownState={resetShowdownState}
            planShowdownChoice={planShowdownChoice}
            runShowdownSessionStep={runShowdownSessionStep}
            executeShowdownNextAction={executeShowdownNextAction}
          />

          {/* Old Showdown console section removed - now using ShowdownConsole component */}

          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">Showdown 控制台</h2>
            <p className="mt-1 text-xs text-gray-500">创建队伍、搜索天梯、连接 websocket，并有界运行自动选择循环。</p>

            {/* Showdown Console Component */}
            <ShowdownConsole
              showdownUsername={showdownUsername}
              setShowdownUsername={setShowdownUsername}
              showdownPassword={showdownPassword}
              setShowdownPassword={setShowdownPassword}
              showdownAutoLogin={showdownAutoLogin}
              setShowdownAutoLogin={setShowdownAutoLogin}
              showdownAutoAccept={showdownAutoAccept}
              setShowdownAutoAccept={setShowdownAutoAccept}
              showdownAutoResearch={showdownAutoResearch}
              setShowdownAutoResearch={setShowdownAutoResearch}
              showdownRunLimit={showdownRunLimit}
              setShowdownRunLimit={setShowdownRunLimit}
              showdownChainRounds={showdownChainRounds}
              setShowdownChainRounds={setShowdownChainRounds}
              showdownLoopChains={showdownLoopChains}
              setShowdownLoopChains={setShowdownLoopChains}
              showdownProgramFormats={showdownProgramFormats}
              setShowdownProgramFormats={setShowdownProgramFormats}
              showdownMode={showdownMode}
              setShowdownMode={setShowdownMode}
              showdownMissionGoal={showdownMissionGoal}
              setShowdownMissionGoal={setShowdownMissionGoal}
              showdownPayload={showdownPayload}
              setShowdownPayload={setShowdownPayload}
              busy={busy}
              showdownSession={showdownSession}
              showdownPlan={showdownPlan}
              showdownRunSummary={showdownRunSummary}
              showdownMissionPlan={showdownMissionPlan}
              showdownTacticalBriefing={showdownTacticalBriefing}
              showdownMatchupBriefing={showdownMatchupBriefing}
              showdownTrainingChain={activeShowdownTrainingChain}
              showdownTrainingLoop={activeShowdownTrainingLoop}
              showdownTrainingProgramPlan={activeShowdownTrainingProgramPlan}
              showdownTrainingProgram={activeShowdownTrainingProgram}
              showdownTrainingProgramPipeline={activeShowdownTrainingProgramPipeline}
              showdownTrainingProgramAutopilot={activeShowdownTrainingProgramAutopilot}
              showdownMastery={showdownMastery}
              showdownTeamKnowledge={showdownTeamKnowledge}
              showdownTeamKnowledgeSummary={showdownTeamKnowledgeSummary}
              showdownChallengeUser={showdownChallengeUser}
              showdownRooms={showdownRooms}
              activeLiveReadiness={activeLiveReadiness}
              activeShowdownLearning={activeShowdownLearning}
              activeTrainingChainTrend={activeTrainingChainTrend}
              showdownTargetPolicy={showdownTargetPolicy}
              selectedFormat={selectedFormat}
              createShowdownSession={createShowdownSession}
              startShowdownMission={startShowdownMission}
              previewShowdownMissionPlan={previewShowdownMissionPlan}
              previewShowdownTacticalBriefing={previewShowdownTacticalBriefing}
              previewShowdownTrainingProgram={previewShowdownTrainingProgram}
              runShowdownTrainingChain={runShowdownTrainingChain}
              runShowdownTrainingLoop={runShowdownTrainingLoop}
              runShowdownTrainingProgram={runShowdownTrainingProgram}
              runShowdownTrainingProgramPipeline={runShowdownTrainingProgramPipeline}
              runShowdownTrainingProgramAutopilot={runShowdownTrainingProgramAutopilot}
              startShowdownSearch={startShowdownSearch}
              connectShowdownSession={connectShowdownSession}
              refreshShowdownReadiness={refreshShowdownReadiness}
              refreshShowdownMatchupBriefing={refreshShowdownMatchupBriefing}
              runLiveShowdownOnce={runLiveShowdownOnce}
              runLiveShowdownUntil={runLiveShowdownUntil}
              runShowdownAutopilot={runShowdownAutopilot}
              runShowdownSupervisor={runShowdownSupervisor}
              researchShowdownTeam={researchShowdownTeam}
              cancelShowdownSearch={cancelShowdownSearch}
              acceptShowdownChallenge={acceptShowdownChallenge}
              rejectShowdownChallenge={rejectShowdownChallenge}
              flushShowdownPending={flushShowdownPending}
              closeShowdownSession={closeShowdownSession}
              resetShowdownState={resetShowdownState}
              planShowdownChoice={planShowdownChoice}
              runShowdownSessionStep={runShowdownSessionStep}
              executeShowdownNextAction={executeShowdownNextAction}
            />

          </section>

          {/* Old Showdown console panels removed - now handled by ShowdownConsole component */}

          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">Showdown 控制台</h2>
            <p className="mt-1 text-xs text-gray-500">创建队伍、搜索天梯、连接 websocket，并有界运行自动选择循环。</p>
          </section>

          {/* Old Showdown console panels removed - now handled by ShowdownConsole component */}

          <section className="card p-4">
            <h2 className="text-lg font-semibold text-white">Showdown 控制台</h2>
            <p className="mt-1 text-xs text-gray-500">创建队伍、搜索天梯、连接 websocket，并有界运行自动选择循环。</p>
          </section>

          <p className="mt-3 break-all text-xs leading-5 text-gray-600">
            {battleId ? wsURL : '本地对战创建后会显示 WebSocket；真实 PS 会话连接仍继续深化。'}
          </p>
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value, compact = false }: { label: string; value: string | number; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-border bg-black/20 ${compact ? 'p-3' : 'p-4'}`}>
      <div className="text-xs uppercase text-gray-500">{label}</div>
      <div className={`${compact ? 'mt-1 text-lg' : 'mt-2 text-2xl'} min-w-0 break-words font-semibold text-white`}>{value}</div>
    </div>
  );
}
