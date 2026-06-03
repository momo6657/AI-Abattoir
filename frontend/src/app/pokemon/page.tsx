'use client';

import { useEffect, useMemo, useState } from 'react';
import BattleField from './components/BattleField';
import TeamManager from './components/TeamManager';
import MoveSelector from './components/MoveSelector';
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
  const [selectedFormat, setSelectedFormat] = useState('vgc2024');
  const [analysis, setAnalysis] = useState<any>(null);
  const [knowledgeQuery, setKnowledgeQuery] = useState('Incineroar');
  const [knowledge, setKnowledge] = useState<any>(null);
  const [showdownPayload, setShowdownPayload] = useState(SAMPLE_SHOWDOWN_PAYLOAD);
  const [showdownUsername, setShowdownUsername] = useState('PokemonBot');
  const [showdownPassword, setShowdownPassword] = useState('');
  const [showdownAutoLogin, setShowdownAutoLogin] = useState(true);
  const [showdownRunLimit, setShowdownRunLimit] = useState(10);
  const [showdownMode, setShowdownMode] = useState<'auto' | 'balanced' | 'aggressive' | 'defensive'>('auto');
  const [showdownPlan, setShowdownPlan] = useState<any>(null);
  const [showdownSession, setShowdownSession] = useState<any>(null);
  const [showdownAnalysis, setShowdownAnalysis] = useState<any>(null);
  const [showdownLearning, setShowdownLearning] = useState<any>(null);
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

  useEffect(() => {
    refreshOverview();
  }, []);

  function addMessage(message: string) {
    setMessages((prev) => [message, ...prev].slice(0, 14));
  }

  async function refreshOverview() {
    try {
      const [speciesRes, movesRes, historyRes, formatsRes] = await Promise.all([
        pokemonApi.listSpecies(),
        pokemonApi.listMoves(),
        pokemonApi.getHistory(8),
        pokemonApi.listFormats(),
      ]);
      setSpeciesCount(speciesRes.data.length || 0);
      setMoveCount(movesRes.data.length || 0);
      setHistory(historyRes.data || []);
      const nextFormats = formatsRes.data || [];
      setFormats(nextFormats);
      if (nextFormats.length && !nextFormats.some((format: PokemonFormat) => format.id === selectedFormat)) {
        setSelectedFormat(nextFormats[0].id);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '无法读取 Pokemon 模块状态');
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

  async function planShowdownChoice() {
    if (!showdownPayload.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = (await pokemonApi.planShowdownDecision({
        payload: showdownPayload,
        mode: showdownMode,
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
      login_password: showdownPassword || undefined,
      auto_search: autoSearch,
    })).data;
    setShowdownSession(session);
    setShowdownAnalysis(session.analysis || null);
    addMessage(`Showdown session ready: ${session.showdown_format}`);
    return session;
  }

  async function createShowdownSession(autoSearch = false) {
    setBusy(true);
    setError(null);
    try {
      const session = await ensureShowdownSession(autoSearch);
      setShowdownSession(session);
      addMessage(autoSearch ? 'Showdown session created with ladder search queued.' : 'Showdown session created.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '创建 Showdown 会话失败');
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
      setShowdownSession(result.session);
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
      setShowdownSession(result.session);
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
      setShowdownSession(result.session);
      addMessage(`Cancel search queued: ${(result.commands || []).join(' / ')}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '取消搜索失败');
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
      setShowdownSession(result.session);
      addMessage(`Connected to Showdown, sent ${result.sent?.length || 0} pending command(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '连接 Showdown websocket 失败');
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
      setShowdownSession(result.session);
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
      setShowdownSession(result.session);
      setShowdownAnalysis(result.session?.analysis || showdownAnalysis);
      setShowdownLearning(result.learning_profile || showdownLearning);
      const steps = result.steps || [];
      const lastDecision = [...steps].reverse().find((step: any) => step.decision)?.decision;
      setShowdownPlan(lastDecision || showdownPlan);
      addMessage(`Auto run stopped at ${result.session?.status || 'ready'} after ${steps.length} message(s).`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '自动运行 Showdown 会话失败');
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
      setShowdownSession(session);
      addMessage('Showdown websocket closed.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '关闭 Showdown 会话失败');
    } finally {
      setBusy(false);
    }
  }

  const phaseItems = [
    ['Phase 1', '本地双打引擎、伤害计算、REST 流程、训练 UI'],
    ['Phase 2', '知识检索、缓存、决策记录、强化学习雏形'],
    ['Phase 3', '等级驱动队伍构建、对战分析、经验进化'],
    ['Phase 4', '多格式目录、Showdown 队伍上传、会话运行器和自动选择命令'],
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
                  setShowdownSession(null);
                  setShowdownAnalysis(null);
                  setShowdownLearning(null);
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

          <section className="card p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white">Showdown 控制台</h2>
                <p className="mt-1 text-xs text-gray-500">创建队伍、搜索天梯、连接 websocket，并有界运行自动选择循环。</p>
              </div>
              <button
                onClick={() => setShowdownPayload(SAMPLE_SHOWDOWN_PAYLOAD)}
                className="rounded-md border border-border px-2 py-1 text-xs text-gray-300 hover:border-accent"
              >
                示例
              </button>
            </div>

            <div className="mt-3 grid grid-cols-[minmax(0,1fr)_88px] gap-2">
              <label className="text-xs text-gray-500">
                Username
                <input
                  value={showdownUsername}
                  onChange={(event) => setShowdownUsername(event.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm normal-case text-gray-100 outline-none focus:border-accent"
                />
              </label>
              <label className="text-xs text-gray-500">
                Steps
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={showdownRunLimit}
                  onChange={(event) => setShowdownRunLimit(Math.max(1, Math.min(50, Number(event.target.value) || 1)))}
                  className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm normal-case text-gray-100 outline-none focus:border-accent"
                />
              </label>
            </div>
            <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
              <label className="text-xs text-gray-500">
                Password
                <input
                  value={showdownPassword}
                  onChange={(event) => setShowdownPassword(event.target.value)}
                  type="password"
                  className="mt-1 w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm normal-case text-gray-100 outline-none focus:border-accent"
                  placeholder="optional"
                />
              </label>
              <label className="mt-5 flex items-center gap-2 rounded-md border border-border bg-black/20 px-3 py-2 text-xs text-gray-300">
                <input
                  type="checkbox"
                  checked={showdownAutoLogin}
                  onChange={(event) => setShowdownAutoLogin(event.target.checked)}
                  className="h-4 w-4 accent-accent"
                />
                Auto login
              </label>
            </div>

            <div className="mt-3 grid grid-cols-4 gap-1 rounded-md border border-border bg-black/20 p-1">
              {(['auto', 'balanced', 'aggressive', 'defensive'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setShowdownMode(mode)}
                  className={`rounded px-2 py-1.5 text-xs transition ${
                    showdownMode === mode ? 'bg-accent text-white' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2">
              <button onClick={() => createShowdownSession(false)} disabled={busy} className="btn-secondary disabled:opacity-50">
                创建会话
              </button>
              <button onClick={startShowdownSearch} disabled={busy} className="btn-primary disabled:opacity-50">
                搜索天梯
              </button>
              <button onClick={connectShowdownSession} disabled={busy} className="btn-secondary disabled:opacity-50">
                连接 PS
              </button>
              <button onClick={runLiveShowdownOnce} disabled={busy || !showdownSession?.session_id} className="btn-secondary disabled:opacity-50">
                跑一步
              </button>
              <button onClick={runLiveShowdownUntil} disabled={busy || !showdownSession?.session_id} className="btn-primary disabled:opacity-50">
                自动运行
              </button>
              <button onClick={cancelShowdownSearch} disabled={busy || !showdownSession?.session_id} className="btn-secondary disabled:opacity-50">
                取消搜索
              </button>
              <button onClick={closeShowdownSession} disabled={busy || !showdownSession?.session_id} className="btn-secondary disabled:opacity-50">
                关闭连接
              </button>
              <button
                onClick={() => {
                  setShowdownSession(null);
                  setShowdownAnalysis(null);
                  setShowdownLearning(null);
                  setShowdownPlan(null);
                }}
                disabled={busy}
                className="btn-secondary disabled:opacity-50"
              >
                重置
              </button>
            </div>

            <div className="mt-3 rounded-md border border-border bg-black/20 px-3 py-2 text-xs text-gray-400">
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">Showdown format</span>
                <span className="break-all text-right font-mono text-gray-200">
                  {selectedFormatInfo?.showdown_format || selectedFormat}
                </span>
              </div>
            </div>

            <textarea
              value={showdownPayload}
              onChange={(event) => setShowdownPayload(event.target.value)}
              rows={6}
              className="mt-3 w-full resize-none rounded-md border border-border bg-black/30 px-3 py-2 font-mono text-xs leading-5 text-gray-200 outline-none focus:border-accent"
              spellCheck={false}
            />

            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                onClick={planShowdownChoice}
                disabled={busy || !showdownPayload.trim()}
                className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
              >
                生成选择
              </button>
              <button
                onClick={runShowdownSessionStep}
                disabled={busy || !showdownPayload.trim()}
                className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                推进会话
              </button>
            </div>

            <div className="mt-3 rounded-md border border-border bg-black/20 p-3 text-xs leading-5 text-gray-400">
              {showdownPlan ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-500">Type</span>
                    <span className="text-gray-200">{showdownPlan.decision_type}</span>
                  </div>
                  <div className="break-all rounded bg-black/30 p-2 font-mono text-gray-100">
                    {showdownPlan.command || 'waiting'}
                  </div>
                  <div>{showdownPlan.reason}</div>
                  {showdownPlan.choice_details?.length ? (
                    <div className="space-y-1">
                      {showdownPlan.choice_details.map((detail: any, index: number) => (
                        <div key={`${detail.choice || detail.move || 'choice'}-${index}`} className="rounded bg-black/30 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-gray-200">{detail.choice || detail.move || 'choice'}</span>
                            {detail.score !== undefined && <span className="text-gray-500">score {detail.score}</span>}
                          </div>
                          <div className="mt-1 text-gray-500">{detail.reason}</div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : (
                '等待 Showdown payload。'
              )}
            </div>

            <div className="mt-3 rounded-md border border-border bg-black/20 p-3 text-xs leading-5 text-gray-400">
              {showdownSession ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-500">Session</span>
                    <span className="text-gray-200">{showdownSession.status}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-500">Mode</span>
                    <span className="text-gray-200">
                      {showdownSession.mode}
                      {showdownSession.requested_mode === 'auto' ? ' · auto' : ''}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-500">Team</span>
                    <span className="text-right text-gray-200">{showdownSession.team_source || 'none'}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <Metric label="Auto Login" value={showdownSession.auto_login ? 'on' : 'off'} compact />
                    <Metric label="Assertion" value={showdownSession.has_login_assertion ? 'ready' : 'none'} compact />
                  </div>
                  {showdownSession.team_species?.length ? (
                    <div className="rounded bg-black/30 p-2 text-gray-500">
                      {showdownSession.team_species.join(' / ')}
                    </div>
                  ) : null}
                  {showdownSession.team_reason && (
                    <div className="rounded bg-black/30 p-2 text-gray-500">
                      {showdownSession.team_reason}
                    </div>
                  )}
                  {showdownSession.mode_recommendation?.reason && (
                    <div className="rounded bg-black/30 p-2 text-gray-500">
                      {showdownSession.mode_recommendation.reason}
                    </div>
                  )}
                  <div className="break-all font-mono text-gray-500">{showdownSession.session_id}</div>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <Metric label="Pending" value={showdownSession.pending_command_count ?? 0} compact />
                    <Metric label="Sent" value={showdownSession.sent_count ?? 0} compact />
                    <Metric label="Events" value={showdownSession.event_count ?? 0} compact />
                    <Metric label="Decisions" value={showdownSession.decision_count ?? 0} compact />
                  </div>
                  {showdownSession.last_command && (
                    <div className="break-all rounded bg-black/30 p-2 font-mono text-gray-500">
                      {showdownSession.last_command}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <Metric label="Reward" value={showdownAnalysis?.reward ?? 0} compact />
                    <Metric label="Result" value={showdownAnalysis?.status ?? 'in_progress'} compact />
                    <Metric label="Turns" value={showdownAnalysis?.turns ?? 0} compact />
                    <Metric label="Faints" value={showdownAnalysis?.faints ?? 0} compact />
                  </div>
                  {showdownLearning && (
                    <div className="rounded-md border border-border bg-black/20 p-2">
                      <div className="grid grid-cols-2 gap-2">
                        <Metric label="Win Rate" value={`${Math.round((showdownLearning.win_rate || 0) * 100)}%`} compact />
                        <Metric label="Avg Reward" value={Number(showdownLearning.average_reward || 0).toFixed(1)} compact />
                      </div>
                      <div className="mt-2 text-gray-500">
                        Suggested mode: <span className="text-gray-200">{showdownLearning.recommendation?.mode || 'balanced'}</span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                '推进会话后会记录登录、搜索、对战选择和结果状态。'
              )}
            </div>

            <p className="mt-3 break-all text-xs leading-5 text-gray-600">
              {battleId ? wsURL : '本地对战创建后会显示 WebSocket；真实 PS 会话连接仍继续深化。'}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value, compact = false }: { label: string; value: string | number; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-border bg-black/20 ${compact ? 'p-3' : 'p-4'}`}>
      <div className="text-xs uppercase text-gray-500">{label}</div>
      <div className={`${compact ? 'mt-1 text-lg' : 'mt-2 text-2xl'} font-semibold text-white`}>{value}</div>
    </div>
  );
}
