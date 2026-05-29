"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  agentsApi,
  arenaApi,
  conversationsApi,
  gamesApi,
  healthApi,
  modelsApi,
} from "@/lib/api";
import { getStatusLabel } from "@/lib/utils";

type EntityStatus = "idle" | "loading" | "ready" | "degraded";

interface DashboardStats {
  models: number;
  agents: number;
  conversations: number;
  games: number;
  arenaMatches: number;
  activeGames: number;
  activeConversations: number;
}

interface HealthState {
  status: EntityStatus;
  database: string;
  api: string;
}

interface ActivityItem {
  id: string;
  title: string;
  status?: string;
  href: string;
  meta: string;
}

const DEFAULT_STATS: DashboardStats = {
  models: 0,
  agents: 0,
  conversations: 0,
  games: 0,
  arenaMatches: 0,
  activeGames: 0,
  activeConversations: 0,
};

const MODULES = [
  { title: "模型接入", href: "/models", metric: "models", accent: "from-sky-400/20 to-cyan-300/10" },
  { title: "智能体", href: "/agents", metric: "agents", accent: "from-emerald-400/20 to-lime-300/10" },
  { title: "对话", href: "/conversations", metric: "conversations", accent: "from-amber-400/20 to-orange-300/10" },
  { title: "游戏", href: "/games", metric: "games", accent: "from-rose-400/20 to-red-300/10" },
] as const;

const QUICK_ACTIONS = [
  { label: "添加模型", href: "/models", hint: "连接新的 LLM 提供商" },
  { label: "创建智能体", href: "/agents", hint: "设定人格、能力与提示词" },
  { label: "发起对话", href: "/conversations", hint: "让多个智能体协作或辩论" },
  { label: "开启游戏", href: "/games", hint: "进入狼人杀、谈判或文字冒险" },
];

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function isActiveStatus(status?: string) {
  return status === "active" || status === "in_progress" || status === "voting";
}

function StatPill({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/22 px-3 py-2">
      <div className="text-lg font-semibold text-white">{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-flex h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.8)]" : "bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,0.75)]"}`}
    />
  );
}

export default function Home() {
  const [stats, setStats] = useState<DashboardStats>(DEFAULT_STATS);
  const [health, setHealth] = useState<HealthState>({
    status: "idle",
    database: "unknown",
    api: "unknown",
  });
  const [recentItems, setRecentItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      setLoading(true);
      const [models, agents, conversations, games, matches, healthResult] = await Promise.allSettled([
        modelsApi.list(),
        agentsApi.list(),
        conversationsApi.list(),
        gamesApi.list(),
        arenaApi.listMatches(),
        healthApi.get(),
      ]);

      if (!mounted) return;

      const modelRows = models.status === "fulfilled" ? asArray<Record<string, unknown>>(models.value.data) : [];
      const agentRows = agents.status === "fulfilled" ? asArray<Record<string, unknown>>(agents.value.data) : [];
      const conversationRows = conversations.status === "fulfilled" ? asArray<Record<string, unknown>>(conversations.value.data) : [];
      const gameRows = games.status === "fulfilled" ? asArray<Record<string, unknown>>(games.value.data) : [];
      const matchRows = matches.status === "fulfilled" ? asArray<Record<string, unknown>>(matches.value.data) : [];
      const healthData = healthResult.status === "fulfilled" ? healthResult.value.data as { status?: string; database?: string } : null;

      setStats({
        models: modelRows.length,
        agents: agentRows.length,
        conversations: conversationRows.length,
        games: gameRows.length,
        arenaMatches: matchRows.length,
        activeGames: gameRows.filter((game) => isActiveStatus(String(game.status || ""))).length,
        activeConversations: conversationRows.filter((conversation) => isActiveStatus(String(conversation.status || ""))).length,
      });

      setHealth({
        status: healthData?.status === "ok" ? "ready" : "degraded",
        database: healthData?.database || "unavailable",
        api: healthData?.status || "unavailable",
      });

      const recentConversations = conversationRows.slice(0, 2).map((item) => ({
        id: String(item.id),
        title: String(item.title || "未命名对话"),
        status: item.status ? String(item.status) : undefined,
        href: "/conversations",
        meta: "对话",
      }));
      const recentGames = gameRows.slice(0, 2).map((item) => ({
        id: String(item.id),
        title: String(item.title || "未命名游戏"),
        status: item.status ? String(item.status) : undefined,
        href: "/games",
        meta: "游戏",
      }));

      setRecentItems([...recentConversations, ...recentGames]);
      setLoading(false);
    }

    loadDashboard();
    return () => {
      mounted = false;
    };
  }, []);

  const readiness = useMemo(() => {
    if (health.status === "ready" && stats.models > 0 && stats.agents > 0) return "ready";
    if (health.status === "ready") return "setup";
    return "degraded";
  }, [health.status, stats.agents, stats.models]);

  return (
    <div className="animate-fade-in space-y-8">
      <section className="relative min-h-[460px] overflow-hidden rounded-lg border border-white/10 bg-black/35">
        <Image
          src="/images/ai-abattoir-hero.png"
          alt=""
          fill
          priority
          className="object-cover opacity-58"
          sizes="(min-width: 1280px) 1216px, 100vw"
        />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(7,8,13,0.96)_0%,rgba(7,8,13,0.78)_42%,rgba(7,8,13,0.18)_100%)]" />
        <div className="relative z-10 flex min-h-[460px] flex-col justify-between p-6 sm:p-8 lg:p-10">
          <div className="max-w-2xl">
            <div className="mb-5 inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-gray-300">
              <StatusDot ok={health.status === "ready"} />
              {health.status === "idle" || loading ? "正在同步系统状态" : health.status === "ready" ? "后端与数据库在线" : "后端连接异常"}
            </div>
            <h1 className="max-w-2xl text-4xl font-bold tracking-normal text-white sm:text-5xl lg:text-6xl">
              AI Abattoir
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-gray-300 sm:text-lg">
              多模型智能体的对话、竞技、游戏与进化控制台。把模型接入、角色编排和实时观战放在同一个工作台里。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/agents" className="btn-primary px-5 py-3">创建智能体</Link>
              <Link href="/games" className="btn-secondary px-5 py-3">进入游戏房间</Link>
            </div>
          </div>

          <div className="grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
            <StatPill label="模型" value={loading ? "--" : stats.models} />
            <StatPill label="智能体" value={loading ? "--" : stats.agents} />
            <StatPill label="活跃对话" value={loading ? "--" : stats.activeConversations} />
            <StatPill label="活跃游戏" value={loading ? "--" : stats.activeGames} />
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {MODULES.map((module) => (
            <Link
              href={module.href}
              key={module.href}
              className="card-hover group overflow-hidden p-5"
            >
              <div className={`mb-5 h-1.5 w-20 rounded-full bg-gradient-to-r ${module.accent}`} />
              <div className="flex items-end justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-white">{module.title}</h2>
                  <p className="mt-1 text-sm text-gray-400">
                    {module.metric === "models" && "统一管理 LLM 接入配置"}
                    {module.metric === "agents" && "维护角色、等级和能力侧写"}
                    {module.metric === "conversations" && "组织自由讨论、辩论与接力"}
                    {module.metric === "games" && "运行博弈、冒险和社交推理"}
                  </p>
                </div>
                <div className="text-3xl font-bold text-white">
                  {loading ? "--" : stats[module.metric]}
                </div>
              </div>
            </Link>
          ))}
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-white">系统就绪度</h2>
              <p className="mt-1 text-sm text-gray-400">
                {readiness === "ready" && "模型、智能体与后端状态完整"}
                {readiness === "setup" && "后端在线，建议补齐模型或智能体"}
                {readiness === "degraded" && "需要检查后端服务或数据库连接"}
              </p>
            </div>
            <span className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
              readiness === "ready"
                ? "bg-emerald-400/10 text-emerald-300"
                : readiness === "setup"
                  ? "bg-amber-400/10 text-amber-300"
                  : "bg-red-400/10 text-red-300"
            }`}>
              {readiness === "ready" ? "Ready" : readiness === "setup" ? "Setup" : "Degraded"}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-surface-overlay p-3">
              <div className="text-xs text-gray-500">API</div>
              <div className="mt-1 truncate text-sm text-gray-200">{health.api}</div>
            </div>
            <div className="rounded-lg bg-surface-overlay p-3">
              <div className="text-xs text-gray-500">Database</div>
              <div className="mt-1 truncate text-sm text-gray-200">{health.database}</div>
            </div>
            <div className="rounded-lg bg-surface-overlay p-3">
              <div className="text-xs text-gray-500">竞技场</div>
              <div className="mt-1 text-sm text-gray-200">{loading ? "--" : `${stats.arenaMatches} 场比赛`}</div>
            </div>
            <div className="rounded-lg bg-surface-overlay p-3">
              <div className="text-xs text-gray-500">总工作流</div>
              <div className="mt-1 text-sm text-gray-200">{loading ? "--" : stats.conversations + stats.games}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="card p-5">
          <h2 className="font-semibold text-white">快捷动作</h2>
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
            {QUICK_ACTIONS.map((action) => (
              <Link
                href={action.href}
                key={action.href}
                className="rounded-lg border border-border bg-surface-overlay p-4 transition-colors hover:border-border-hover hover:bg-surface-overlay/80"
              >
                <div className="font-medium text-white">{action.label}</div>
                <div className="mt-1 text-sm text-gray-400">{action.hint}</div>
              </Link>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white">近期工作流</h2>
            <Link href="/spectate" className="text-sm text-accent-hover hover:text-white">观战中心</Link>
          </div>
          <div className="mt-4 space-y-2">
            {recentItems.length > 0 ? recentItems.map((item) => (
              <Link
                key={`${item.meta}-${item.id}`}
                href={item.href}
                className="flex items-center justify-between gap-4 rounded-lg border border-border bg-surface-overlay px-4 py-3 transition-colors hover:border-border-hover"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-white">{item.title}</div>
                  <div className="text-xs text-gray-500">{item.meta}</div>
                </div>
                {item.status && (
                  <span className="shrink-0 rounded-lg bg-black/25 px-2.5 py-1 text-xs text-gray-300">
                    {getStatusLabel(item.status)}
                  </span>
                )}
              </Link>
            )) : (
              <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-gray-500">
                {loading ? "正在加载近期工作流" : "还没有对话或游戏记录"}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
