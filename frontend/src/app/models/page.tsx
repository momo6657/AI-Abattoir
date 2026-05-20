"use client";

import { useEffect, useState } from "react";
import { modelsApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner, Badge } from "@/components";
import type { Model } from "@/types";

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", provider: "openai", model_id: "", api_key: "" });
  const [editingId, setEditingId] = useState<string | null>(null);

  const loadModels = async () => {
    try {
      setLoading(true);
      const r = await modelsApi.list();
      setModels(r.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadModels(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await modelsApi.update(editingId, form);
      } else {
        await modelsApi.create(form);
      }
      await loadModels();
      setShowForm(false);
      setEditingId(null);
      setForm({ name: "", provider: "openai", model_id: "", api_key: "" });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "操作失败");
    }
  };

  const handleEdit = (model: Model) => {
    setForm({ name: model.name, provider: model.provider, model_id: model.model_id, api_key: "" });
    setEditingId(model.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此模型？")) return;
    try {
      await modelsApi.delete(id);
      await loadModels();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const PROVIDERS = [
    { value: "openai", label: "OpenAI", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
    { value: "anthropic", label: "Anthropic", color: "bg-orange-500/10 text-orange-400 border-orange-500/20" },
    { value: "google", label: "Google", color: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
    { value: "deepseek", label: "DeepSeek", color: "bg-purple-500/10 text-purple-400 border-purple-500/20" },
  ];

  const getProviderStyle = (provider: string) => {
    return PROVIDERS.find(p => p.value === provider)?.color || "bg-gray-500/10 text-gray-400 border-gray-500/20";
  };

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-2xl font-bold">模型管理</h2>
          <p className="text-sm text-gray-400 mt-1">管理 LLM 模型接入配置</p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ name: "", provider: "openai", model_id: "", api_key: "" }); }}
          className="btn-primary"
        >
          添加模型
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-6 mb-6 space-y-4 animate-slide-up">
          <h3 className="text-lg font-semibold">{editingId ? "编辑模型" : "添加新模型"}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">模型名称</label>
              <input
                placeholder="如: GPT-4o"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">提供商</label>
              <select
                value={form.provider}
                onChange={(e) => setForm({ ...form, provider: e.target.value })}
                className="input-field"
              >
                {PROVIDERS.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">模型 ID</label>
              <input
                placeholder="如: gpt-4o"
                value={form.model_id}
                onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">API Key</label>
              <input
                placeholder={editingId ? "留空则不更新" : "sk-..."}
                type="password"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                className="input-field"
              />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary">
              {editingId ? "保存修改" : "添加"}
            </button>
            <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="btn-secondary">
              取消
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-3">
          {models.map((model) => (
            <div key={model.id} className="card-hover p-5 flex justify-between items-center">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-surface-overlay flex items-center justify-center">
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold">{model.name}</h3>
                  <p className="text-sm text-gray-400">{model.model_id}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2.5 py-1 rounded-lg border ${getProviderStyle(model.provider)}`}>
                  {model.provider}
                </span>
                <Badge text={model.status} variant={model.status === "online" ? "success" : "default"} size="md" />
                <button onClick={() => handleEdit(model)} className="btn-ghost text-sm">编辑</button>
                <button onClick={() => handleDelete(model.id)} className="btn-ghost text-sm text-red-400 hover:text-red-300">删除</button>
              </div>
            </div>
          ))}
          {models.length === 0 && (
            <div className="card p-16 text-center">
              <div className="w-16 h-16 rounded-2xl bg-surface-overlay flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <p className="text-gray-400 mb-2">暂无模型</p>
              <p className="text-sm text-gray-500">点击"添加模型"开始配置 LLM 接入</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
