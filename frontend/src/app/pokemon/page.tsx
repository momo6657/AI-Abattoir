'use client';

import { useEffect, useMemo, useState } from 'react';
import BattleField from './components/BattleField';
import TeamManager from './components/TeamManager';
import MoveSelector from './components/MoveSelector';
import { agentsApi, modelsApi, pokemonApi, resolveWebSocketURL } from '@/lib/api';

const MODEL_NAME = 'Pokemon Local Policy';
const RED_AGENT = '红方训练师';
const BLUE_AGENT = '蓝方训练师';

type SetupState = {
  model?: any;
  redAgent?: any;
  blueAgent?: any;
  redTeam?: any;
  blueTeam?: any;
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
  const [analysis, setAnalysis] = useState<any>(null);
  const [knowledgeQuery, setKnowledgeQuery] = useState('Incineroar');
  const [knowledge, setKnowledge] = useState<any>(null);
  const [messages, setMessages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsURL = useMemo(
    () => (battleId ? resolveWebSocketURL(`/ws/pokemon/battle/${battleId}`) : ''),
    [battleId]
  );

  useEffect(() => {
    refreshOverview();
  }, []);

  function addMessage(message: string) {
    setMessages((prev) => [message, ...prev].slice(0, 14));
  }

  async function refreshOverview() {
    try {
      const [speciesRes, movesRes, historyRes] = await Promise.all([
        pokemonApi.listSpecies(),
        pokemonApi.listMoves(),
        pokemonApi.getHistory(8),
      ]);
      setSpeciesCount(speciesRes.data.length || 0);
      setMoveCount(movesRes.data.length || 0);
      setHistory(historyRes.data || []);
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
      addMessage('初始化本地宝可梦数据');
      await pokemonApi.init();
      const model = await getOrCreateModel();
      const redAgent = await getOrCreateAgent(RED_AGENT, model.id, '稳健进攻');
      const blueAgent = await getOrCreateAgent(BLUE_AGENT, model.id, '平衡反制');

      addMessage('自动构建双方模板队伍');
      const [redTeam, blueTeam] = await Promise.all([
        pokemonApi.buildTeam(redAgent.id, 'vgc2024'),
        pokemonApi.buildTeam(blueAgent.id, 'vgc2024'),
      ]);

      addMessage('创建本地 VGC 双打对战');
      const battle = (await pokemonApi.createBattle({
        player1_team_id: redTeam.data.id,
        player2_team_id: blueTeam.data.id,
        battle_format: 'vgc2024',
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

  const phaseItems = [
    ['Phase 1', '本地双打引擎、伤害计算、REST 流程、训练 UI'],
    ['Phase 2', '知识检索、缓存、决策记录、强化学习雏形'],
    ['Phase 3', '等级驱动队伍构建、对战分析、经验进化'],
    ['Phase 4', 'Pokemon Showdown 协议解析已接入，登录/天梯实战仍需继续完善'],
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
          <div className="flex flex-wrap gap-2">
            <button
              onClick={prepareTrainingBattle}
              disabled={busy}
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

        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="Species" value={speciesCount} />
          <Metric label="Moves" value={moveCount} />
          <Metric label="Battles" value={history.length} />
          <Metric label="WebSocket" value={battleId ? 'ready' : 'idle'} />
        </div>
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
            <h2 className="text-lg font-semibold text-white">Showdown 连接</h2>
            <p className="mt-2 break-all text-xs leading-5 text-gray-500">
              {battleId ? wsURL : '创建对战后生成本地实时通道。PS 登录、房间同步和天梯匹配仍属于后续深化任务。'}
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
