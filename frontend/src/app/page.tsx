import Link from "next/link";

const FEATURES = [
  {
    title: "对话引擎",
    desc: "多智能体自由对话、辩论、接力创作",
    href: "/conversations",
    gradient: "from-blue-500/20 to-cyan-500/20",
    iconColor: "text-blue-400",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  {
    title: "竞技场",
    desc: "模型 PK 对决，Elo 排名系统",
    href: "/arena",
    gradient: "from-purple-500/20 to-pink-500/20",
    iconColor: "text-purple-400",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    title: "游戏系统",
    desc: "狼人杀、辩论赛、策略模拟",
    href: "/games",
    gradient: "from-emerald-500/20 to-teal-500/20",
    iconColor: "text-emerald-400",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: "观战中心",
    desc: "实时观看对话和游戏，支持回放",
    href: "/spectate",
    gradient: "from-amber-500/20 to-orange-500/20",
    iconColor: "text-amber-400",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
    ),
  },
  {
    title: "排行榜",
    desc: "智能体综合实力排名与进化追踪",
    href: "/leaderboard",
    gradient: "from-rose-500/20 to-red-500/20",
    iconColor: "text-rose-400",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
    ),
  },
  {
    title: "联网搜索",
    desc: "实时搜索互联网获取最新信息",
    href: "/search",
    gradient: "from-indigo-500/20 to-violet-500/20",
    iconColor: "text-indigo-400",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
];

export default function Home() {
  return (
    <div className="space-y-16 animate-fade-in">
      {/* Hero */}
      <section className="relative text-center py-20 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-radial from-accent/10 via-transparent to-transparent" />
        <div className="relative z-10">
          <h2 className="text-5xl sm:text-6xl font-bold mb-4 tracking-tight">
            <span className="gradient-text">AI Abattoir</span>
          </h2>
          <p className="text-lg text-gray-400 mb-10 max-w-xl mx-auto leading-relaxed">
            让多个 AI 大模型对话、合作、竞争、对抗的交互平台
          </p>
          <div className="flex justify-center gap-4">
            <Link href="/models" className="btn-primary text-base px-8 py-3">
              添加模型
            </Link>
            <Link href="/agents" className="btn-secondary text-base px-8 py-3">
              创建智能体
            </Link>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {FEATURES.map((f) => (
          <Link
            key={f.href}
            href={f.href}
            className="card-hover p-6 group"
          >
            <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${f.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
            <div className="relative">
              <div className={`w-10 h-10 rounded-xl bg-surface-overlay flex items-center justify-center mb-4 ${f.iconColor} group-hover:scale-110 transition-transform duration-200`}>
                {f.icon}
              </div>
              <h3 className="text-lg font-semibold mb-2 group-hover:text-white transition-colors">
                {f.title}
              </h3>
              <p className="text-sm text-gray-400 group-hover:text-gray-300 transition-colors">
                {f.desc}
              </p>
            </div>
          </Link>
        ))}
      </section>

      {/* Quick Stats */}
      <section className="card p-8 text-center">
        <p className="text-gray-400 text-sm">
          支持 100+ 种 LLM 模型接入 · 多模态交互 · 实时 WebSocket 通信 · 经验进化系统
        </p>
      </section>
    </div>
  );
}
