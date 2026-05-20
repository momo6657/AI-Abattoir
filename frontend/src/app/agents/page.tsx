"use client";

import { useEffect, useState, useCallback } from "react";
import { agentsApi, modelsApi } from "@/lib/api";
import { ErrorBanner, Badge, ProgressBar, Modal, LoadingSpinner } from "@/components";

// ---- Types ----
interface Model {
  id: string;
  name: string;
  provider: string;
  model_id: string;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  model_id: string;
  model_name?: string;
  persona?: string;
  personality?: string;
  speaking_style?: string;
  backstory?: string;
  specialties?: string[];
  system_prompt?: string;
  level?: number;
  experience_points?: number;
  max_experience?: number;
  avatar_url?: string;
  created_at: string;
}

interface AgentForm {
  name: string;
  description: string;
  model_id: string;
  persona: string;
  personality: string;
  speaking_style: string;
  backstory: string;
  specialties: string[];
  system_prompt: string;
}

const SPECIALTIES = ["推理", "创意", "代码", "谈判", "领导"];

const TEMPLATES: Record<string, Partial<AgentForm>> = {
  谋略家: {
    name: "谋略家",
    description: "善于制定长期战略和分析复杂局势",
    persona: "你是一位深谋远虑的战略家，擅长从宏观角度分析问题，制定周密的计划。",
    personality: "冷静、理性、深思熟虑，善于发现隐藏的机会和风险",
    speaking_style: "条理清晰，善用类比和历史案例，语气沉稳",
    backstory: "曾经历过无数次危机，每次都能化险为夷，积累了丰富的战略经验。",
    specialties: ["推理", "领导"],
    system_prompt: "",
  },
  执行者: {
    name: "执行者",
    description: "高效执行任务，注重细节和结果",
    persona: "你是一位高效的执行者，接到任务后立即行动，确保高质量完成。",
    personality: "果断、高效、注重细节、结果导向",
    speaking_style: "简洁明了，直奔主题，善用数据说话",
    backstory: "在无数紧急任务中锤炼出钢铁般的执行力，从不允许任何差错。",
    specialties: ["代码", "推理"],
    system_prompt: "",
  },
  创意大师: {
    name: "创意大师",
    description: "天马行空的想象力，善于创造新颖的解决方案",
    persona: "你是一位充满创意的大脑，总能提出令人眼前一亮的新想法。",
    personality: "好奇、开放、富有想象力、不拘一格",
    speaking_style: "生动活泼，善用比喻和故事，偶尔冒出诗意的表达",
    backstory: "从小就在艺术和科技的交叉点上探索，相信创意可以改变世界。",
    specialties: ["创意"],
    system_prompt: "",
  },
  谈判专家: {
    name: "谈判专家",
    description: "精通博弈论和沟通技巧，擅长达成共识",
    persona: "你是一位经验丰富的谈判专家，能够在对立中找到共同利益。",
    personality: "善于倾听、有同理心、灵活应变、追求双赢",
    speaking_style: "温和但有力，善用提问引导对方，偶尔使用幽默化解紧张",
    backstory: "处理过无数复杂的商业谈判和国际争端，深知沟通的艺术。",
    specialties: ["谈判", "领导"],
    system_prompt: "",
  },
  领导者: {
    name: "领导者",
    description: "天生的领袖，善于激励团队和统筹全局",
    persona: "你是一位具有远见卓识的领导者，能够凝聚团队力量达成目标。",
    personality: "自信、有魅力、果断、关怀团队成员",
    speaking_style: "鼓舞人心，善用愿景描述，关键时刻一锤定音",
    backstory: "从基层一步步成长，深知每个角色的价值，因此能够赢得所有人的尊重。",
    specialties: ["领导", "推理"],
    system_prompt: "",
  },
};

const EMPTY_FORM: AgentForm = {
  name: "",
  description: "",
  model_id: "",
  persona: "",
  personality: "",
  speaking_style: "",
  backstory: "",
  specialties: [],
  system_prompt: "",
};

// ---- Helpers ----
function getLevelColor(level: number): string {
  if (level >= 10) return "text-red-400";
  if (level >= 7) return "text-purple-400";
  if (level >= 4) return "text-blue-400";
  return "text-green-400";
}

function getAvatarLetter(name: string): string {
  return name.charAt(0).toUpperCase();
}

function getAvatarBg(index: number): string {
  const colors = [
    "bg-blue-600", "bg-purple-600", "bg-green-600",
    "bg-red-600", "bg-yellow-600", "bg-pink-600",
    "bg-indigo-600", "bg-teal-600",
  ];
  return colors[index % colors.length];
}

// ---- Page Component ----
export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AgentForm>({ ...EMPTY_FORM });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [detailAgent, setDetailAgent] = useState<Agent | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAgents = useCallback(async () => {
    try {
      setLoading(true);
      const r = await agentsApi.list();
      setAgents(r.data);
      setError(null);
    } catch (err) {
      setError("无法加载智能体列表，请检查后端服务是否运行");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadModels = useCallback(async () => {
    try {
      const r = await modelsApi.list();
      setModels(r.data);
    } catch {
      // Models list failure is non-critical
    }
  }, []);

  useEffect(() => {
    loadAgents();
    loadModels();
  }, [loadAgents, loadModels]);

  const resetForm = () => {
    setForm({ ...EMPTY_FORM });
    setEditingId(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const formData = form as unknown as Record<string, unknown>;
      if (editingId) {
        await agentsApi.update(editingId, formData);
      } else {
        await agentsApi.create(formData);
      }
      await loadAgents();
      setShowForm(false);
      resetForm();
    } catch {
      setError("操作失败，请检查网络连接");
    }
  };

  const handleEdit = (agent: Agent) => {
    setForm({
      name: agent.name,
      description: agent.description,
      model_id: agent.model_id,
      persona: agent.persona || "",
      personality: agent.personality || "",
      speaking_style: agent.speaking_style || "",
      backstory: agent.backstory || "",
      specialties: agent.specialties || [],
      system_prompt: agent.system_prompt || "",
    });
    setEditingId(agent.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定要删除这个智能体吗？")) return;
    try {
      await agentsApi.delete(id);
      await loadAgents();
    } catch {
      setError("删除失败");
    }
  };

  const applyTemplate = (templateName: string) => {
    const template = TEMPLATES[templateName];
    if (template) {
      setForm({ ...EMPTY_FORM, ...template });
      setShowTemplates(false);
      setShowForm(true);
    }
  };

  const toggleSpecialty = (s: string) => {
    setForm((prev) => ({
      ...prev,
      specialties: prev.specialties.includes(s)
        ? prev.specialties.filter((x) => x !== s)
        : [...prev.specialties, s],
    }));
  };

  const filteredAgents = agents.filter(
    (a) =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getModelName = (modelId: string) => {
    const m = models.find((x) => x.id === modelId);
    return m ? m.name : modelId;
  };

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h2 className="text-2xl font-bold gradient-text">智能体管理</h2>
          <p className="text-sm text-gray-400 mt-1">创建和管理你的 AI 智能体，赋予它们独特的人格与能力</p>
        </div>
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="搜索智能体..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field w-48"
          />
          <button
            onClick={() => {
              resetForm();
              setShowTemplates(true);
            }}
            className="btn-secondary text-sm"
          >
            模板创建
          </button>
          <button
            onClick={() => {
              resetForm();
              setShowForm(!showForm);
              setShowTemplates(false);
            }}
            className="btn-primary text-sm"
          >
            {showForm ? "取消" : "创建智能体"}
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
      )}

      {/* Templates */}
      {showTemplates && (
        <div className="card p-6 mb-6 animate-slide-up">
          <h3 className="text-lg font-semibold mb-4">选择预设模板</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(TEMPLATES).map(([name, tpl]) => (
              <button
                key={name}
                onClick={() => applyTemplate(name)}
                className="bg-surface-overlay hover:bg-surface-overlay/80 border border-border hover:border-border-hover p-4 rounded-xl text-left transition-all duration-200"
              >
                <h4 className="font-semibold text-white mb-1">{name}</h4>
                <p className="text-sm text-gray-400">{tpl.description}</p>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {tpl.specialties?.map((s) => (
                    <span key={s} className="text-xs bg-accent/20 text-accent-hover px-2 py-0.5 rounded-full">
                      {s}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowTemplates(false)}
            className="btn-ghost mt-4 text-sm"
          >
            取消
          </button>
        </div>
      )}

      {/* Create / Edit Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="card p-6 mb-6 space-y-4 animate-slide-up">
          <h3 className="text-lg font-semibold">{editingId ? "编辑智能体" : "创建智能体"}</h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">名称 *</label>
              <input
                placeholder="智能体名称"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">绑定模型 *</label>
              <select
                value={form.model_id}
                onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                className="input-field"
                required
              >
                <option value="">选择模型</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.provider})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">描述</label>
            <input
              placeholder="简短描述"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">人设描述</label>
            <textarea
              placeholder="角色扮演的基础设定..."
              value={form.persona}
              onChange={(e) => setForm({ ...form, persona: e.target.value })}
              className="input-field h-20 resize-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">性格特征</label>
              <textarea
                placeholder="冷静、理性、幽默..."
                value={form.personality}
                onChange={(e) => setForm({ ...form, personality: e.target.value })}
                className="input-field h-20 resize-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">说话风格</label>
              <textarea
                placeholder="简洁明了、善用比喻..."
                value={form.speaking_style}
                onChange={(e) => setForm({ ...form, speaking_style: e.target.value })}
                className="input-field h-20 resize-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">背景故事</label>
            <textarea
              placeholder="智能体的背景故事..."
              value={form.backstory}
              onChange={(e) => setForm({ ...form, backstory: e.target.value })}
              className="input-field h-20 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">擅长领域</label>
            <div className="flex flex-wrap gap-2">
              {SPECIALTIES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleSpecialty(s)}
                  className={`px-3 py-1.5 rounded-full text-sm transition-all duration-200 ${
                    form.specialties.includes(s)
                      ? "bg-accent text-white shadow-lg shadow-accent/25"
                      : "bg-surface-overlay text-gray-400 border border-border hover:border-border-hover"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">自定义 System Prompt</label>
            <textarea
              placeholder="可选：覆盖默认的 system prompt..."
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
              className="input-field h-24 resize-none"
            />
          </div>

          <div className="flex gap-3">
            <button type="submit" className="btn-primary">
              {editingId ? "保存修改" : "创建"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                resetForm();
              }}
              className="btn-secondary"
            >
              取消
            </button>
          </div>
        </form>
      )}

      {/* Agent Cards */}
      {loading ? (
        <div className="flex justify-center py-16"><LoadingSpinner /></div>
      ) : (
      <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredAgents.map((agent, index) => (
          <div
            key={agent.id}
            className="card-hover p-5 cursor-pointer"
            onClick={() => setDetailAgent(agent)}
          >
            <div className="flex items-start gap-4">
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold text-white flex-shrink-0 ${getAvatarBg(index)}`}
              >
                {getAvatarLetter(agent.name)}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold truncate">{agent.name}</h3>
                <p className="text-sm text-gray-400 truncate">
                  {agent.description || "暂无描述"}
                </p>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge
                  text={`Lv.${agent.level || 1}`}
                  variant={((agent.level || 1) >= 10 ? "danger" : (agent.level || 1) >= 7 ? "info" : (agent.level || 1) >= 4 ? "info" : "success") as "danger" | "info" | "success"}
                  size="sm"
                />
                <span className="text-xs text-gray-500">
                  {getModelName(agent.model_id)}
                </span>
              </div>
              {agent.specialties && agent.specialties.length > 0 && (
                <div className="flex gap-1">
                  {agent.specialties.slice(0, 2).map((s) => (
                    <span key={s} className="text-xs bg-surface-overlay text-gray-400 px-2 py-0.5 rounded-full">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* XP Progress Bar */}
            <div className="mt-3">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>经验值</span>
                <span>
                  {agent.experience_points || 0} / {agent.max_experience || 100}
                </span>
              </div>
              <ProgressBar
                value={Math.min(((agent.experience_points || 0) / (agent.max_experience || 100)) * 100, 100)}
                height="h-1.5"
              />
            </div>

            <div className="mt-3 flex gap-2" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => handleEdit(agent)}
                className="btn-ghost text-xs px-2 py-1"
              >
                编辑
              </button>
              <button
                onClick={() => handleDelete(agent.id)}
                className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded-xl hover:bg-red-900/20 transition-all duration-200"
              >
                删除
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredAgents.length === 0 && (
        <div className="text-center py-20 text-gray-500">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <p className="text-lg">
            {searchQuery ? "没有找到匹配的智能体" : "还没有智能体"}
          </p>
          <p className="text-sm mt-1 text-gray-600">
            {searchQuery ? "试试其他关键词" : "点击上方按钮创建你的第一个智能体"}
          </p>
        </div>
      )}
      </>
      )}

      {/* Detail Modal */}
      {detailAgent && (
        <Modal open onClose={() => setDetailAgent(null)} title={detailAgent.name} maxWidth="max-w-2xl">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-16 h-16 rounded-full bg-accent flex items-center justify-center text-2xl font-bold text-white">
                {getAvatarLetter(detailAgent.name)}
              </div>
              <p className="text-gray-400">{detailAgent.description}</p>
            </div>

            <div className="space-y-4">
              {/* Level & XP */}
              <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-lg font-bold ${getLevelColor(detailAgent.level || 1)}`}>
                    等级 {detailAgent.level || 1}
                  </span>
                  <span className="text-sm text-gray-400">
                    {detailAgent.experience_points || 0} / {detailAgent.max_experience || 100} XP
                  </span>
                </div>
                <ProgressBar
                  value={Math.min(((detailAgent.experience_points || 0) / (detailAgent.max_experience || 100)) * 100, 100)}
                />
              </div>

              {/* Model */}
              <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                <h4 className="text-sm text-gray-400 mb-1">绑定模型</h4>
                <p>{getModelName(detailAgent.model_id)}</p>
              </div>

              {/* Specialties */}
              {detailAgent.specialties && detailAgent.specialties.length > 0 && (
                <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                  <h4 className="text-sm text-gray-400 mb-2">擅长领域</h4>
                  <div className="flex flex-wrap gap-2">
                    {detailAgent.specialties.map((s) => (
                      <span key={s} className="bg-accent/20 text-accent-hover px-3 py-1 rounded-full text-sm">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {detailAgent.persona && (
                <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                  <h4 className="text-sm text-gray-400 mb-1">人设描述</h4>
                  <p className="text-sm">{detailAgent.persona}</p>
                </div>
              )}

              {detailAgent.personality && (
                <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                  <h4 className="text-sm text-gray-400 mb-1">性格特征</h4>
                  <p className="text-sm">{detailAgent.personality}</p>
                </div>
              )}

              {detailAgent.speaking_style && (
                <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                  <h4 className="text-sm text-gray-400 mb-1">说话风格</h4>
                  <p className="text-sm">{detailAgent.speaking_style}</p>
                </div>
              )}

              {detailAgent.backstory && (
                <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                  <h4 className="text-sm text-gray-400 mb-1">背景故事</h4>
                  <p className="text-sm">{detailAgent.backstory}</p>
                </div>
              )}

              {detailAgent.system_prompt && (
                <div className="bg-surface-overlay rounded-xl p-4 border border-border">
                  <h4 className="text-sm text-gray-400 mb-1">自定义 System Prompt</h4>
                  <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono">
                    {detailAgent.system_prompt}
                  </pre>
                </div>
              )}
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => {
                  setDetailAgent(null);
                  handleEdit(detailAgent);
                }}
                className="btn-primary text-sm"
              >
                编辑
              </button>
              <button
                onClick={() => setDetailAgent(null)}
                className="btn-secondary text-sm"
              >
                关闭
              </button>
            </div>
        </Modal>
      )}
    </div>
  );
}
