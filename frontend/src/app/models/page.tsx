"use client";

import { useEffect, useState } from "react";
import { modelsApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner, Badge } from "@/components";
import type { Model } from "@/types";
import { extractErrorMessage } from "@/lib/errors";

interface ModelForm {
  name: string;
  provider: string;
  model_id: string;
  api_key: string;
  api_base: string;
}

function emptyForm(): ModelForm {
  return { name: "", provider: "custom", model_id: "", api_key: "", api_base: "" };
}

function deriveProvider(apiBase: string): string {
  try {
    const url = new URL(apiBase.startsWith("http") ? apiBase : `https://${apiBase}`);
    const host = url.hostname.toLowerCase();
    const known: Record<string, string> = {
      "api.openai.com": "openai",
      "api.anthropic.com": "anthropic",
      "generativelanguage.googleapis.com": "google",
      "api.deepseek.com": "deepseek",
    };
    return known[host] || host.slice(0, 50) || "custom";
  } catch {
    return "custom";
  }
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ModelForm>(emptyForm());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [discoverMessage, setDiscoverMessage] = useState("");

  const loadModels = async () => {
    try {
      setLoading(true);
      const r = await modelsApi.list();
      setModels(r.data);
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "加载失败"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadModels(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: Record<string, unknown> = {
        ...form,
        provider: form.provider || deriveProvider(form.api_base),
        api_base: form.api_base.trim(),
      };
      if (editingId && !form.api_key.trim()) {
        delete payload.api_key;
      }
      if (editingId) {
        await modelsApi.update(editingId, payload);
      } else {
        await modelsApi.create(payload);
      }
      await loadModels();
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm());
      setDiscoveredModels([]);
      setDiscoverMessage("");
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "操作失败"));
    }
  };

  const handleEdit = (model: Model) => {
    setForm({
      name: model.name,
      provider: model.provider || "custom",
      model_id: model.model_id,
      api_key: "",
      api_base: model.api_base || "",
    });
    setDiscoveredModels([]);
    setDiscoverMessage("");
    setEditingId(model.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此模型？")) return;
    try {
      await modelsApi.delete(id);
      await loadModels();
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "删除失败"));
    }
  };

  const handleDiscoverModels = async () => {
    if (!form.api_base.trim()) {
      setError("请先填写 API URL");
      return;
    }
    try {
      setDiscovering(true);
      setDiscoverMessage("");
      const r = await modelsApi.discover({
        api_base: form.api_base.trim(),
        api_key: form.api_key.trim() || undefined,
      });
      const modelIds = r.data.models as string[];
      setDiscoveredModels(modelIds);
      setForm(prev => ({
        ...prev,
        api_base: r.data.api_base || prev.api_base,
        provider: r.data.provider || deriveProvider(r.data.api_base || prev.api_base),
        model_id: prev.model_id || modelIds[0] || "",
        name: prev.name || modelIds[0] || "",
      }));
      setDiscoverMessage(`已获取 ${modelIds.length} 个模型`);
    } catch (e: unknown) {
      setDiscoveredModels([]);
      setDiscoverMessage("");
      setError(extractErrorMessage(e, "获取模型列表失败"));
    } finally {
      setDiscovering(false);
    }
  };

  const getProviderStyle = (provider: string) => {
    const styles: Record<string, string> = {
      openai: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      anthropic: "bg-orange-500/10 text-orange-400 border-orange-500/20",
      google: "bg-blue-500/10 text-blue-400 border-blue-500/20",
      deepseek: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    };
    return styles[provider] || "bg-cyan-500/10 text-cyan-300 border-cyan-500/20";
  };

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-2xl font-bold">模型管理</h2>
          <p className="text-sm text-gray-400 mt-1">管理 LLM 模型接入配置</p>
        </div>
        <button
          onClick={() => {
            setShowForm(!showForm);
            setEditingId(null);
            setForm(emptyForm());
            setDiscoveredModels([]);
            setDiscoverMessage("");
          }}
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
                placeholder="如: GPT-4o 或 DeepSeek V3"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">API URL</label>
              <input
                placeholder="如: https://api.openai.com/v1"
                value={form.api_base}
                onChange={(e) => setForm({ ...form, api_base: e.target.value, provider: deriveProvider(e.target.value) })}
                className="input-field"
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">模型 ID</label>
              {discoveredModels.length > 0 ? (
                <select
                  value={form.model_id}
                  onChange={(e) => setForm({ ...form, model_id: e.target.value, name: form.name || e.target.value })}
                  className="input-field"
                  required
                >
                  {discoveredModels.map(modelId => (
                    <option key={modelId} value={modelId}>{modelId}</option>
                  ))}
                </select>
              ) : (
                <input
                  placeholder="如: gpt-4o，也可先点击获取模型"
                  value={form.model_id}
                  onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                  className="input-field"
                  required
                />
              )}
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
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleDiscoverModels}
              disabled={discovering}
              className="btn-secondary"
            >
              {discovering ? "获取中..." : "自动获取模型"}
            </button>
            <span className="text-sm text-gray-400">
              {discoverMessage || "支持 OpenAI 兼容的 /v1/models 接口，URL 可填写根地址或 /v1 地址"}
            </span>
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
                  {model.api_base && (
                    <p className="mt-1 max-w-[520px] truncate text-xs text-gray-500">{model.api_base}</p>
                  )}
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
